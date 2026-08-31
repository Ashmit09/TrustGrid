"""
TrustGrid Trust Engine.

Responsibilities
----------------
1. Accept a behavioral feature vector (from feature_engine).
2. Run XGBoost ML model to get an overall reliability probability.
3. Map features to five per-dimension scores (0–100 each).
4. Blend ML reliability score with rule-based dimension scores.
5. Apply the per-role weighted formula.
6. Convert to a 0–1000 Trust Score.
7. Apply score smoothing to prevent wild swings.
8. Clamp the result to [0, 1000].
9. Persist the new score + history to the database.

ML Integration
--------------
The XGBoost model (pre-trained on synthetic data) outputs P(reliable=1) ∈ [0,1].
This probability is blended with the rule-based dimension calculation:

    final_raw = β × ml_adjusted_raw + (1 − β) × rule_based_raw

where β depends on evidence (decayed_event_weight):
    β = 0.0  for very new users (weight < 1)    → pure rule-based
    β = 0.3  for medium evidence (weight 1–10)
    β = 0.5  for strong evidence (weight > 10)

This ensures:
  - New users get the rule-based neutral starting score.
  - Users with more data gradually benefit from ML-driven scoring.
  - The system degrades gracefully if the ML model is unavailable.

Design notes
------------
• Score smoothing formula:
      new_score = α × model_score + (1 − α) × previous_score
  where α depends on confidence:
      LOW  → α = 0.20, MEDIUM → α = 0.50, HIGH → α = 0.80

• Per-role dimension weights:
    BUYER:  25% / 25% / 20% / 15% / 15%
    SELLER: 25% / 25% / 20% / 15% / 15%

• Every dimension produces a score in [0, 100].
• RawScore = weighted sum (already in [0, 100]).
• TrustScore = 10 × RawScore → [0, 1000].
"""
from datetime import datetime, timezone
from typing import Dict, Optional

from sqlalchemy.orm import Session

from app.models.trust import (
    TrustScore, ScoreHistory, ConfidenceLevel, TrustTier,
)
from app.models.user import UserRole
from app.trustgrid.confidence_service import calculate_confidence
from app.trustgrid.ml_service import (
    get_buyer_reliability_score,
    get_seller_reliability_score,
)


# ── Smoothing alphas ──────────────────────────────────────────────────────────

_ALPHA: Dict[str, float] = {
    ConfidenceLevel.LOW:    0.20,
    ConfidenceLevel.MEDIUM: 0.50,
    ConfidenceLevel.HIGH:   0.80,
}

# ── Tier thresholds ───────────────────────────────────────────────────────────

def score_to_tier(score: int) -> TrustTier:
    if score >= 800:
        return TrustTier.ELITE
    if score >= 600:
        return TrustTier.TRUSTED
    if score >= 400:
        return TrustTier.STANDARD
    return TrustTier.RESTRICTED


# ── Public entry point ────────────────────────────────────────────────────────

def recalculate_trust_score(
    db: Session,
    user_id: str,
    role: UserRole,
    features: dict,
    account_created_at: Optional[datetime] = None,
    event_type: Optional[str] = None,
    reason: Optional[str] = None,
) -> TrustScore:
    """
    Full pipeline:
      features → dimension scores → weighted score → smooth → clamp → persist.

    Parameters
    ----------
    db                 : active session (must be after features are committed)
    user_id            : BUY-xxxxx or SEL-xxxxx
    role               : UserRole.buyer or UserRole.seller
    features           : dict from feature_engine.get_feature_vector()
    account_created_at : for confidence calculation
    event_type         : optional label for score history record
    reason             : optional human-readable reason for score history

    Returns
    -------
    Updated TrustScore ORM row.
    """
    # 1. Compute per-dimension scores (0–100)
    if role == UserRole.buyer:
        dim_scores = _buyer_dimensions(features)
        rule_raw   = _buyer_weighted(dim_scores)
        ml_prob    = get_buyer_reliability_score(features)
    else:
        dim_scores = _seller_dimensions(features)
        rule_raw   = _seller_weighted(dim_scores)
        # Only use ML for sellers if they have received at least one rating.
        # Without ratings, avg_rating_received=0.0 confuses the model because
        # "no rating yet" looks identical to "terrible rating" in the feature space.
        has_ratings = features.get("avg_rating_received", 0.0) > 0.0
        ml_prob    = get_seller_reliability_score(features) if has_ratings else None

    # 2. Blend ML output with rule-based score (if ML model available)
    evidence_weight = features.get("decayed_event_weight", 0.0)
    final_raw = _blend_ml(rule_raw, ml_prob, evidence_weight)

    # 3. Convert to 0–1000
    model_score = _clamp(round(final_raw * 10))

    # 4. Confidence
    confidence = calculate_confidence(db, user_id, account_created_at)

    # 5. Retrieve current score (never None — user_service creates it at registration)
    trust_row = db.query(TrustScore).filter(TrustScore.user_id == user_id).first()
    if trust_row is None:
        # Fallback: should not happen in normal flow
        trust_row = TrustScore(
            user_id=user_id,
            trust_score=700,
            confidence=ConfidenceLevel.LOW,
            tier=TrustTier.TRUSTED,
        )
        db.add(trust_row)
        db.flush()

    old_score = trust_row.trust_score

    # 6. Smoothing — blend model score with existing score
    alpha      = _ALPHA[confidence]
    smoothed   = _clamp(round(alpha * model_score + (1 - alpha) * old_score))

    # 7. Tier
    new_tier = score_to_tier(smoothed)

    # 8. Persist score history if there was a meaningful change
    score_change = smoothed - old_score
    if score_change != 0:
        history = ScoreHistory(
            user_id=user_id,
            old_score=old_score,
            new_score=smoothed,
            score_change=score_change,
            reason=reason,
            event_type=event_type,
            created_at=datetime.now(timezone.utc),
        )
        db.add(history)

    # 8. Update TrustScore row
    trust_row.trust_score  = smoothed
    trust_row.confidence   = confidence
    trust_row.tier         = new_tier
    trust_row.dim_scores   = {k: round(v, 2) for k, v in dim_scores.items()}
    trust_row.last_updated = datetime.now(timezone.utc)

    db.commit()
    db.refresh(trust_row)
    return trust_row


# ── Buyer dimension calculations ──────────────────────────────────────────────

def _buyer_dimensions(f: dict) -> Dict[str, float]:
    """
    Map feature vector to five buyer dimension scores (0–100).

    D1 — Order Reliability (25 %)
        Measures successful order completion.
        A new user (order_completion_rate=1.0) starts at 70 not 100
        because there is no evidence yet — we blend with evidence.

    D2 — Return Behaviour (25 %)
        Low return rate = high score.
        A return rate of 0 (no returns) = 100.
        We do NOT heavily penalise low return volumes — only high rates.

    D3 — Payment Reliability (20 %)
        payment_success_rate maps directly.

    D4 — Cancellation Behaviour (15 %)
        Low cancellation rate = high score.

    D5 — Platform Engagement (15 %)
        Referrals + reviews contribute positively.
        Absence of engagement does NOT penalise — only positive signals.
    """
    # D1: Order Reliability
    ocr = f.get("order_completion_rate", 1.0)
    d1 = _rate_to_score(ocr)

    # D2: Return Behaviour — 0 returns → perfect, high rate → penalty
    rr = f.get("return_rate", 0.0)
    # Generous curve: return_rate ≤ 0.10 (10%) → full score, scales down above
    if rr <= 0.10:
        d2 = 100.0
    elif rr <= 0.30:
        # Linear from 100 to 60 between 10% and 30%
        d2 = 100.0 - (rr - 0.10) / 0.20 * 40.0
    else:
        # Steeper penalty above 30%
        d2 = max(20.0, 60.0 - (rr - 0.30) / 0.70 * 40.0)

    # D3: Payment Reliability
    psr = f.get("payment_success_rate", 1.0)
    d3 = _rate_to_score(psr)

    # D4: Cancellation Behaviour
    cr = f.get("cancellation_rate", 0.0)
    # cancellation_rate 0 → 100, ≥ 0.50 → 20
    if cr <= 0.05:
        d4 = 100.0
    elif cr <= 0.30:
        d4 = 100.0 - (cr - 0.05) / 0.25 * 50.0
    else:
        d4 = max(20.0, 50.0 - (cr - 0.30) / 0.70 * 30.0)

    # D5: Platform Engagement (only positive signals)
    referrals = f.get("referral_count", 0)
    reviews   = f.get("review_count",   0)
    # Every referral = +8 pts (capped at 40), every review = +4 pts (capped at 40)
    # Base = 60 (no engagement doesn't penalise heavily)
    engagement_boost = min(40.0, referrals * 8.0) + min(40.0, reviews * 4.0)
    d5 = min(100.0, 60.0 + engagement_boost)

    return {
        "order_reliability":      round(d1, 2),
        "return_behaviour":       round(d2, 2),
        "payment_reliability":    round(d3, 2),
        "cancellation_behaviour": round(d4, 2),
        "platform_engagement":    round(d5, 2),
    }


def _buyer_weighted(d: Dict[str, float]) -> float:
    """
    Weighted raw score for buyers (result is in 0–100).

    RawScore = 0.25×D1 + 0.25×D2 + 0.20×D3 + 0.15×D4 + 0.15×D5
    """
    return (
        0.25 * d["order_reliability"]      +
        0.25 * d["return_behaviour"]       +
        0.20 * d["payment_reliability"]    +
        0.15 * d["cancellation_behaviour"] +
        0.15 * d["platform_engagement"]
    )


# ── Seller dimension calculations ─────────────────────────────────────────────

def _seller_dimensions(f: dict) -> Dict[str, float]:
    """
    Map feature vector to five seller dimension scores (0–100).

    D1 — Order Fulfillment (25 %)
        fulfillment_rate: fulfilled / (fulfilled + seller_cancelled)

    D2 — Delivery Performance (25 %)
        late_delivery_rate: late / delivered — low is good.

    D3 — Customer Satisfaction (20 %)
        avg_rating_received (1–5 star scale).
        0 ratings (new seller) → neutral 70.

    D4 — Return & Dispute Handling (15 %)
        return_response_rate: how quickly/consistently seller handles returns.

    D5 — Platform Reliability (15 %)
        products_listed provides a positive signal (active seller).
    """
    # D1: Fulfillment
    fr = f.get("fulfillment_rate", 1.0)
    d1 = _rate_to_score(fr)

    # D2: Delivery Performance — low late rate = high score
    ldr = f.get("late_delivery_rate", 0.0)
    if ldr <= 0.05:
        d2 = 100.0
    elif ldr <= 0.20:
        d2 = 100.0 - (ldr - 0.05) / 0.15 * 40.0
    else:
        d2 = max(20.0, 60.0 - (ldr - 0.20) / 0.80 * 40.0)

    # D3: Customer Satisfaction from avg rating (1–5 scale → 0–100)
    avg_rating = f.get("avg_rating_received", 0.0)
    if avg_rating == 0.0:
        d3 = 70.0    # neutral — no ratings yet
    else:
        # 5 stars → 100, 1 star → 20, linear
        d3 = max(20.0, 20.0 + (avg_rating - 1.0) / 4.0 * 80.0)

    # D4: Return & Dispute Handling
    rrr = f.get("return_response_rate", 1.0)
    d4 = _rate_to_score(rrr)

    # D5: Platform Reliability — products listed positive signal
    listed = f.get("products_listed", 0)
    listing_boost = min(40.0, listed * 5.0)
    d5 = min(100.0, 60.0 + listing_boost)

    return {
        "order_fulfillment":       round(d1, 2),
        "delivery_performance":    round(d2, 2),
        "customer_satisfaction":   round(d3, 2),
        "return_dispute_handling": round(d4, 2),
        "platform_reliability":    round(d5, 2),
    }


def _seller_weighted(d: Dict[str, float]) -> float:
    """
    Weighted raw score for sellers (result is in 0–100).

    RawScore = 0.25×D1 + 0.25×D2 + 0.20×D3 + 0.15×D4 + 0.15×D5
    """
    return (
        0.25 * d["order_fulfillment"]       +
        0.25 * d["delivery_performance"]    +
        0.20 * d["customer_satisfaction"]   +
        0.15 * d["return_dispute_handling"] +
        0.15 * d["platform_reliability"]
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _blend_ml(
    rule_raw: float,
    ml_prob: Optional[float],
    evidence_weight: float,
) -> float:
    """
    Blend ML-derived reliability probability with rule-based raw score.

    Parameters
    ----------
    rule_raw        : rule-based weighted raw score (0–100)
    ml_prob         : XGBoost P(reliable=1) ∈ [0,1], or None if model unavailable
    evidence_weight : decayed_event_weight from feature vector

    Returns
    -------
    Blended raw score in [0, 100].

    Blending weight β grows with evidence:
      weight < 1  → β = 0.0 (pure rule-based for brand-new users)
      weight 1–10 → β = 0.3
      weight > 10 → β = 0.5

    The ML probability is mapped to a 0–100 score by interpreting it
    as a reliability level:  ml_raw = 20 + ml_prob × 80
    (same range as _rate_to_score, so the blend is comparable in scale).
    """
    if ml_prob is None:
        return rule_raw  # graceful fallback — model not available

    # Map ML probability to same 0–100 scale
    ml_raw = 20.0 + ml_prob * 80.0

    # Choose blend weight based on evidence
    if evidence_weight < 1.0:
        beta = 0.0
    elif evidence_weight < 10.0:
        beta = 0.3
    else:
        beta = 0.5

    return beta * ml_raw + (1 - beta) * rule_raw


def _rate_to_score(rate: float) -> float:
    """
    Linear mapping: rate (0.0–1.0) → score (20–100).
    A rate of 1.0 → 100, a rate of 0.0 → 20.
    Minimum of 20 prevents any single dimension from hitting 0.
    """
    return max(20.0, min(100.0, 20.0 + rate * 80.0))


def _clamp(value: int) -> int:
    return max(0, min(1000, value))
