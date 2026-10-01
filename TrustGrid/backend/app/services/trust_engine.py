"""
TrustGrid — Trust Engine

Implements the complete end-to-end algorithm from spec §28.

STEP 1–2  : Load + age events (handled by Feature Engine)
STEP 3    : Build decayed behavioral features
STEP 4    : Calculate five rule-based dimensions
STEP 5    : Compute RuleScore
STEP 6    : XGBoost prediction (or safe fallback)
STEP 7    : Calculate Confidence
STEP 8    : Select ML weight β
STEP 9    : CombinedScore = (1−β)·RuleScore + β·MLScore
STEP 10   : Smoothing: New100 = (1−α)·Previous100 + α·CombinedScore
STEP 11   : Cold-start exception
STEP 12   : TrustScore = clamp(round(New100 × 10), 0, 1000)
STEP 13   : Determine tier
STEP 14   : Determine privileges
STEP 15   : Generate explanation
STEP 16   : Store trust state + score history

All frozen formulas and constants are imported from app.core.constants.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.constants import (
    INITIAL_TRUST_SCORE, INITIAL_TRUST_SCORE_100,
    ML_BETA, SMOOTHING_ALPHA,
    LOW_MAX_EVENTS,
)
from app.services.feature_engine import build_features
from app.services.dimension_scorer import calculate_dimensions, compute_rule_score
from app.services.confidence import get_confidence
from app.services.tier_service import get_tier
from app.services.privilege_engine import get_privileges
from app.services.explanation_service import generate_explanation
from app.models.trust_score import TrustScore
from app.models.score_history import ScoreHistory


# ── ML Service placeholder (replaced in Phase 14) ────────────────────────────

def _ml_predict(features: Dict, role: str) -> Optional[float]:
    """
    Attempt XGBoost prediction.  Returns probability in [0,1] or None on failure.
    Phase 14 replaces this stub with the real model call.
    """
    try:
        from app.services.ml_service import predict
        return predict(features, role)
    except Exception:
        return None


# ── Main Engine ────────────────────────────────────────────────────────────────

def run_trust_engine(
    db: Session,
    user_id: str,
    role: str,
    events: List[Dict[str, Any]],
    *,
    reference_ts: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Run the full TrustGrid algorithm for a user and persist the result.

    Parameters
    ----------
    db           : SQLAlchemy session
    user_id      : logical user ID (BUY-xxxxx or SEL-xxxxx)
    role         : 'buyer' | 'seller'
    events       : list of raw trust event dicts (from event_service)
    reference_ts : calculation timestamp (default: now)

    Returns
    -------
    Full TrustGrid state dict suitable for API responses.
    """
    if reference_ts is None:
        reference_ts = datetime.now(timezone.utc)

    # ── STEP 3: Build features ────────────────────────────────────────────────
    features = build_features(events, role, reference_ts=reference_ts)

    # ── STEP 4: Dimensions ────────────────────────────────────────────────────
    dimensions = calculate_dimensions(features, role)

    # ── STEP 5: RuleScore (0–100) ─────────────────────────────────────────────
    rule_score = compute_rule_score(dimensions, role)

    # ── STEP 6: ML prediction ─────────────────────────────────────────────────
    ml_probability = _ml_predict(features, role)
    ml_score = (ml_probability * 100.0) if ml_probability is not None else None

    # ── STEP 7: Confidence ────────────────────────────────────────────────────
    meaningful_count = features["meaningful_event_count"]
    confidence = get_confidence(meaningful_count)

    # ── STEP 8: β (ML weight) ────────────────────────────────────────────────
    beta = ML_BETA[confidence]

    # ── STEP 9: CombinedScore ─────────────────────────────────────────────────
    if ml_score is not None and beta > 0.0:
        combined_score = (1.0 - beta) * rule_score + beta * ml_score
    else:
        combined_score = rule_score          # No ML contribution for LOW or missing model

    # ── STEP 10 + 11: Smoothing + Cold-start ─────────────────────────────────
    prev_state = db.query(TrustScore).filter(TrustScore.user_id == user_id).first()
    is_new_user = prev_state is None or meaningful_count <= LOW_MAX_EVENTS

    if is_new_user and meaningful_count == 0:
        # Absolute cold start: preserve 700 exactly
        new_100 = float(INITIAL_TRUST_SCORE_100)
    else:
        alpha = SMOOTHING_ALPHA[confidence]
        prev_100 = (prev_state.trust_score / 10.0) if prev_state else INITIAL_TRUST_SCORE_100
        new_100 = (1.0 - alpha) * prev_100 + alpha * combined_score

    # ── STEP 12: Convert 0–1000 ───────────────────────────────────────────────
    trust_score_int = max(0, min(1000, round(new_100 * 10)))

    # ── STEP 13: Tier ────────────────────────────────────────────────────────
    tier = get_tier(trust_score_int)

    # ── STEP 14: Privileges ───────────────────────────────────────────────────
    privileges = get_privileges(trust_score_int, confidence, tier, role)

    # ── STEP 15: Explanation ──────────────────────────────────────────────────
    old_score = prev_state.trust_score if prev_state else INITIAL_TRUST_SCORE
    explanation = generate_explanation(
        role=role,
        dimensions=dimensions,
        rule_score=rule_score,
        ml_score=ml_score,
        combined_score=combined_score,
        confidence=confidence,
        old_score=old_score,
        new_score=trust_score_int,
    )

    # ── STEP 16: Persist ─────────────────────────────────────────────────────
    if prev_state is None:
        ts_row = TrustScore(
            user_id=user_id,
            trust_score=trust_score_int,
            confidence=confidence,
            tier=tier,
            last_updated=reference_ts,
        )
        db.add(ts_row)
    else:
        prev_state.trust_score = trust_score_int
        prev_state.confidence = confidence
        prev_state.tier = tier
        prev_state.last_updated = reference_ts

    score_change = trust_score_int - old_score
    history_row = ScoreHistory(
        user_id=user_id,
        old_score=old_score,
        new_score=trust_score_int,
        score_change=score_change,
        reason=explanation["summary"],
        event_type="TRUST_RECALCULATION",
        created_at=reference_ts,
    )
    db.add(history_row)
    db.commit()

    return {
        "user_id":        user_id,
        "trust_score":    trust_score_int,
        "confidence":     confidence,
        "tier":           tier,
        "breakdown":      dimensions,
        "rule_score":     round(rule_score, 2),
        "ml_score":       round(ml_score, 2) if ml_score is not None else None,
        "combined_score": round(combined_score, 2),
        "benefits":       privileges,
        "explanation":    explanation,
    }
