"""
TrustGrid REST API — /trust/* endpoints.

Endpoints
---------
GET  /trust/me                  → current user's full TrustGrid profile
GET  /trust/{user_id}           → any user's TrustGrid profile (auth required)
GET  /trust/{user_id}/history   → paginated score-change history
GET  /trust/{user_id}/breakdown → per-dimension scores
GET  /trust/{user_id}/benefits  → active + inactive privileges
GET  /trust/{user_id}/explain   → human-readable explanation
GET  /trust/{user_id}/export    → download full score history as CSV
POST /trust/{user_id}/simulate  → what-if simulation (how many events to next tier)
POST /trust/events              → manually fire a trust event (admin only)
POST /trust/referral            → claim a referral reward
POST /trust/refresh             → manually trigger recalculation (admin only)
"""
import csv
import io
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.dependencies import get_current_user_payload, require_role
from app.models.trust import TrustScore, ScoreHistory, Privilege, ConfidenceLevel
from app.models.user import User, UserRole
from app.schemas.trust import TrustProfileOut, ScoreChangeOut, PrivilegeOut
from app.services import trust_service
from app.trustgrid.privilege_engine import get_active_privilege_names, get_all_privilege_details
from app.trustgrid.explanation_service import (
    get_buyer_recommendations,
    get_seller_recommendations,
    label_for_event,
    describe_score_change,
)
from app.trustgrid.feature_engine import get_feature_vector
from app.trustgrid.event_types import EventType
from app.trustgrid.event_service import record_event, update_features_for_users
from app.services.referral_service import complete_referral
from pydantic import BaseModel


router = APIRouter()


# ── Response helpers ──────────────────────────────────────────────────────────

def _build_profile(db: Session, user_id: str) -> TrustProfileOut:
    """Build a full TrustProfileOut for the given user_id."""
    row: Optional[TrustScore] = (
        db.query(TrustScore).filter(TrustScore.user_id == user_id).first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="TrustGrid profile not found.")

    # Recent score history (last 10)
    history = (
        db.query(ScoreHistory)
        .filter(ScoreHistory.user_id == user_id)
        .order_by(ScoreHistory.created_at.desc())
        .limit(10)
        .all()
    )

    # Active benefit names
    benefits = get_active_privilege_names(db, user_id)

    return TrustProfileOut(
        user_id=user_id,
        trust_score=row.trust_score,
        confidence=row.confidence.value if hasattr(row.confidence, "value") else row.confidence,
        tier=row.tier.value if hasattr(row.tier, "value") else row.tier,
        breakdown=row.dim_scores or {},
        recent_changes=[ScoreChangeOut.model_validate(h) for h in history],
        benefits=benefits,
        last_updated=row.last_updated,
    )


# ── GET /trust/me ─────────────────────────────────────────────────────────────

@router.get("/me", response_model=TrustProfileOut, summary="My TrustGrid profile")
def get_my_trust_profile(
    payload: dict = Depends(get_current_user_payload),
    db: Session = Depends(get_db),
):
    """Return the authenticated user's full TrustGrid profile."""
    return _build_profile(db, payload["sub"])


# ── GET /trust/{user_id} ──────────────────────────────────────────────────────

@router.get("/{user_id}", response_model=TrustProfileOut, summary="User's TrustGrid profile")
def get_trust_profile(
    user_id: str,
    payload: dict = Depends(get_current_user_payload),
    db: Session = Depends(get_db),
):
    """
    Return another user's TrustGrid profile.
    Users can only view their own profile unless they are admin.
    """
    requester_id   = payload["sub"]
    requester_role = payload.get("role", "")

    if requester_id != user_id and requester_role != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own TrustGrid profile.",
        )

    return _build_profile(db, user_id)


# ── GET /trust/{user_id}/history ─────────────────────────────────────────────

class ScoreHistoryOut(BaseModel):
    old_score:    int
    new_score:    int
    score_change: int
    reason:       Optional[str]
    event_type:   Optional[str]
    created_at:   str

    model_config = {"from_attributes": True}


@router.get("/{user_id}/history", summary="Score change history")
def get_score_history(
    user_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    payload: dict = Depends(get_current_user_payload),
    db: Session = Depends(get_db),
):
    """Return paginated score-change history for a user."""
    requester_id   = payload["sub"]
    requester_role = payload.get("role", "")

    if requester_id != user_id and requester_role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Access denied.")

    rows = (
        db.query(ScoreHistory)
        .filter(ScoreHistory.user_id == user_id)
        .order_by(ScoreHistory.created_at.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "old_score":    r.old_score,
            "new_score":    r.new_score,
            "score_change": r.score_change,
            "reason":       r.reason,
            "event_type":   r.event_type,
            "created_at":   r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


# ── GET /trust/{user_id}/breakdown ────────────────────────────────────────────

@router.get("/{user_id}/breakdown", summary="Dimension score breakdown")
def get_score_breakdown(
    user_id: str,
    payload: dict = Depends(get_current_user_payload),
    db: Session = Depends(get_db),
):
    """Return per-dimension score breakdown + improvement recommendations."""
    requester_id   = payload["sub"]
    requester_role = payload.get("role", "")

    if requester_id != user_id and requester_role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Access denied.")

    row = db.query(TrustScore).filter(TrustScore.user_id == user_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="TrustGrid profile not found.")

    dim = row.dim_scores or {}

    # Determine role for recommendations
    user = db.query(User).filter(User.user_id == user_id).first()
    if user and user.role == UserRole.buyer:
        recs = get_buyer_recommendations(dim)
    else:
        recs = get_seller_recommendations(dim)

    return {
        "user_id":         user_id,
        "trust_score":     row.trust_score,
        "confidence":      row.confidence.value if hasattr(row.confidence, "value") else row.confidence,
        "tier":            row.tier.value if hasattr(row.tier, "value") else row.tier,
        "breakdown":       dim,
        "recommendations": recs,
    }


# ── GET /trust/{user_id}/benefits ─────────────────────────────────────────────

@router.get("/{user_id}/benefits", summary="User privileges and benefits")
def get_user_benefits(
    user_id: str,
    payload: dict = Depends(get_current_user_payload),
    db: Session = Depends(get_db),
):
    """Return all privileges (active + inactive) for a user."""
    requester_id   = payload["sub"]
    requester_role = payload.get("role", "")

    if requester_id != user_id and requester_role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Access denied.")

    user = db.query(User).filter(User.user_id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")

    privileges = (
        db.query(Privilege)
        .filter(Privilege.user_id == user_id)
        .all()
    )

    # Enrich with label + description from definitions
    defns = {d["name"]: d for d in get_all_privilege_details(user.role)}
    result = []
    for p in privileges:
        defn = defns.get(p.privilege_name, {})
        result.append({
            "name":        p.privilege_name,
            "label":       defn.get("label", p.privilege_name),
            "description": defn.get("description", ""),
            "status":      p.status,
            "reason":      p.reason,
        })

    # Ensure all defined privileges appear (even if no DB row yet)
    existing_names = {p.privilege_name for p in privileges}
    for defn in get_all_privilege_details(user.role):
        if defn["name"] not in existing_names:
            ts = db.query(TrustScore).filter(TrustScore.user_id == user_id).first()
            score = ts.trust_score if ts else 700
            result.append({
                "name":        defn["name"],
                "label":       defn["label"],
                "description": defn["description"],
                "status":      "inactive",
                "reason":      f"Requires Trust Score ≥ {defn['min_score']}.",
            })

    return {"user_id": user_id, "benefits": result}


# ── GET /trust/{user_id}/explain ─────────────────────────────────────────────

@router.get("/{user_id}/explain", summary="Score explanation and why score changed")
def get_score_explanation(
    user_id: str,
    payload: dict = Depends(get_current_user_payload),
    db: Session = Depends(get_db),
):
    """
    Return a human-readable explanation of:
    - Why the current score is what it is (top driving factors)
    - Recent score-change events with plain-English reasons
    - Which dimensions are strong/weak
    - The time-decay note (recent activity > old activity)
    """
    requester_id   = payload["sub"]
    requester_role = payload.get("role", "")
    if requester_id != user_id and requester_role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Access denied.")

    row = db.query(TrustScore).filter(TrustScore.user_id == user_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="TrustGrid profile not found.")

    user = db.query(User).filter(User.user_id == user_id).first()
    dim  = row.dim_scores or {}

    # Identify strongest and weakest dimensions
    if dim:
        sorted_dims = sorted(dim.items(), key=lambda x: x[1])
        weakest  = sorted_dims[:2]   # bottom 2
        strongest = sorted_dims[-2:] # top 2
    else:
        weakest = strongest = []

    # Recent score history (last 8)
    history = (
        db.query(ScoreHistory)
        .filter(ScoreHistory.user_id == user_id)
        .order_by(ScoreHistory.created_at.desc())
        .limit(8)
        .all()
    )

    # Format history entries with human-readable labels
    history_out = []
    for h in history:
        label = label_for_event(h.event_type) if h.event_type else "Score updated"
        history_out.append({
            "score_change": h.score_change,
            "label":        label,
            "reason":       h.reason or describe_score_change(h.score_change, h.event_type),
            "created_at":   h.created_at.isoformat() if h.created_at else None,
        })

    # Improvement recommendations
    if user and user.role == UserRole.buyer:
        recs = get_buyer_recommendations(dim)
    else:
        recs = get_seller_recommendations(dim)

    # Feature vector for context
    features = get_feature_vector(db, user_id)

    # Build driving factors narrative
    factors = _build_driving_factors(row.trust_score, dim, features, user.role if user else UserRole.buyer)

    return {
        "user_id":        user_id,
        "trust_score":    row.trust_score,
        "confidence":     row.confidence.value if hasattr(row.confidence, "value") else row.confidence,
        "tier":           row.tier.value if hasattr(row.tier, "value") else row.tier,
        "driving_factors": factors,
        "strongest_dimensions": [
            {"name": k.replace("_", " ").title(), "score": round(v, 1)} for k, v in strongest
        ],
        "weakest_dimensions": [
            {"name": k.replace("_", " ").title(), "score": round(v, 1)} for k, v in weakest
        ],
        "recent_changes":     history_out,
        "recommendations":    recs,
        "time_decay_note":    "Recent activity has a greater influence on your Trust Score than older activity.",
    }


def _build_driving_factors(
    score: int,
    dim: dict,
    features: dict,
    role: UserRole,
) -> list:
    """
    Build a list of top driving factors with plain-English descriptions.
    Returns items like: {"factor": "Strong payment reliability", "sentiment": "positive"}
    """
    factors = []

    if role == UserRole.buyer:
        if features.get("payment_success_rate", 1.0) >= 0.90:
            factors.append({"factor": "Strong payment history", "sentiment": "positive"})
        elif features.get("payment_success_rate", 1.0) < 0.70:
            factors.append({"factor": "Payment failures are reducing your score", "sentiment": "negative"})

        if features.get("order_completion_rate", 1.0) >= 0.85:
            factors.append({"factor": "Consistent order completions", "sentiment": "positive"})
        elif features.get("order_completion_rate", 1.0) < 0.60:
            factors.append({"factor": "Incomplete orders are affecting your score", "sentiment": "negative"})

        if features.get("cancellation_rate", 0.0) <= 0.10:
            factors.append({"factor": "Low cancellation rate", "sentiment": "positive"})
        elif features.get("cancellation_rate", 0.0) > 0.30:
            factors.append({"factor": "High cancellation rate is lowering your score", "sentiment": "negative"})

        if features.get("return_rate", 0.0) > 0.25:
            factors.append({"factor": "Elevated return rate is affecting your score", "sentiment": "negative"})
        elif features.get("return_rate", 0.0) <= 0.05 and features.get("completed_orders", 0) > 0:
            factors.append({"factor": "Very low return rate", "sentiment": "positive"})

        if features.get("referral_count", 0) > 0:
            factors.append({"factor": f"{int(features['referral_count'])} successful referral(s)", "sentiment": "positive"})

    else:  # seller
        if features.get("fulfillment_rate", 1.0) >= 0.90:
            factors.append({"factor": "High order fulfillment rate", "sentiment": "positive"})
        elif features.get("fulfillment_rate", 1.0) < 0.70:
            factors.append({"factor": "Order fulfillment issues are reducing your score", "sentiment": "negative"})

        avg_r = features.get("avg_rating_received", 0.0)
        if avg_r >= 4.0:
            factors.append({"factor": f"Strong customer ratings ({avg_r:.1f}★)", "sentiment": "positive"})
        elif 0 < avg_r < 3.0:
            factors.append({"factor": "Low customer ratings are affecting your score", "sentiment": "negative"})

        if features.get("late_delivery_rate", 0.0) <= 0.08:
            factors.append({"factor": "On-time delivery record", "sentiment": "positive"})
        elif features.get("late_delivery_rate", 0.0) > 0.25:
            factors.append({"factor": "Late deliveries are lowering your score", "sentiment": "negative"})

        if features.get("return_response_rate", 1.0) >= 0.90:
            factors.append({"factor": "Responsive return handling", "sentiment": "positive"})
        elif features.get("return_response_rate", 1.0) < 0.60:
            factors.append({"factor": "Poor return response rate is hurting your score", "sentiment": "negative"})

    if not factors:
        factors.append({"factor": "Building your Trust Score with activity", "sentiment": "neutral"})

    return factors[:5]


# ── POST /trust/{user_id}/simulate ───────────────────────────────────────────

class SimulateRequest(BaseModel):
    extra_completions:    int = 0
    extra_cancellations:  int = 0
    extra_returns:        int = 0
    extra_payments:       int = 0


@router.post("/{user_id}/simulate", summary="What-if score simulation")
def simulate_score(
    user_id: str,
    body: SimulateRequest,
    payload: dict = Depends(get_current_user_payload),
    db: Session = Depends(get_db),
):
    """
    Simulate how the trust score would change if the user performed additional
    marketplace actions.  This is a read-only projection — nothing is saved.

    The simulation works by:
    1. Fetching the current feature vector.
    2. Applying the requested hypothetical events to the feature counts.
    3. Re-running the dimension + blending + smoothing pipeline.
    4. Returning projected score, tier, and confidence alongside the delta.
    """
    requester_id   = payload["sub"]
    requester_role = payload.get("role", "")
    if requester_id != user_id and requester_role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Access denied.")

    # Validate inputs — cap at 100 per call to prevent abuse
    for field in (body.extra_completions, body.extra_cancellations,
                  body.extra_returns, body.extra_payments):
        if field < 0 or field > 100:
            raise HTTPException(status_code=400, detail="Event counts must be between 0 and 100.")

    user = db.query(User).filter(User.user_id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")

    row = db.query(TrustScore).filter(TrustScore.user_id == user_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="TrustGrid profile not found.")

    # Load current feature vector
    features = get_feature_vector(db, user_id)

    # ── Project hypothetical feature changes ──────────────────────────────────
    projected = dict(features)  # shallow copy — all values are primitives

    ec = body.extra_completions
    en = body.extra_cancellations
    er = body.extra_returns
    ep = body.extra_payments

    if user.role == UserRole.buyer:
        # Completions: also add to total_orders
        new_total_orders       = projected.get("total_orders", 0) + ec + en
        new_completed_orders   = projected.get("completed_orders", 0) + ec
        new_total_cancellations = projected.get("total_cancellations", 0) + en
        new_total_returns      = projected.get("total_returns", 0) + er
        new_successful_payments = projected.get("successful_payments", projected.get("payment_attempts", 0)) + ep
        new_payment_attempts   = projected.get("payment_attempts", 0) + ep

        # Recalculate rates
        if new_total_orders > 0:
            projected["order_completion_rate"] = new_completed_orders / new_total_orders
            projected["cancellation_rate"]     = new_total_cancellations / new_total_orders
        if new_completed_orders > 0:
            projected["return_rate"] = new_total_returns / new_completed_orders
        if new_payment_attempts > 0:
            projected["payment_success_rate"] = new_successful_payments / new_payment_attempts

        projected["total_orders"]         = new_total_orders
        projected["completed_orders"]     = new_completed_orders
        projected["total_cancellations"]  = new_total_cancellations
        projected["total_returns"]        = new_total_returns
        projected["payment_attempts"]     = new_payment_attempts
        projected["successful_payments"]  = new_successful_payments
        # Increase evidence weight for completions
        projected["decayed_event_weight"] = projected.get("decayed_event_weight", 0.0) + ec

    else:  # seller
        new_fulfilled   = projected.get("fulfilled_orders", 0) + ec
        new_cancelled   = projected.get("seller_cancellations", 0) + en
        total_attempts  = new_fulfilled + new_cancelled
        if total_attempts > 0:
            projected["fulfillment_rate"] = new_fulfilled / total_attempts
        projected["fulfilled_orders"]      = new_fulfilled
        projected["seller_cancellations"]  = new_cancelled
        projected["decayed_event_weight"]  = projected.get("decayed_event_weight", 0.0) + ec

    # ── Run the projection through the trust engine (no DB writes) ────────────
    from app.trustgrid.trust_engine import (
        _buyer_dimensions, _seller_dimensions,
        _buyer_weighted, _seller_weighted,
        _blend_ml, _clamp, score_to_tier,
    )
    from app.trustgrid.ml_service import (
        get_buyer_reliability_score, get_seller_reliability_score,
    )

    if user.role == UserRole.buyer:
        dim_scores = _buyer_dimensions(projected)
        rule_raw   = _buyer_weighted(dim_scores)
        ml_prob    = get_buyer_reliability_score(projected)
    else:
        dim_scores = _seller_dimensions(projected)
        rule_raw   = _seller_weighted(dim_scores)
        has_ratings = projected.get("avg_rating_received", 0.0) > 0.0
        ml_prob    = get_seller_reliability_score(projected) if has_ratings else None

    evidence_weight = projected.get("decayed_event_weight", 0.0)
    final_raw       = _blend_ml(rule_raw, ml_prob, evidence_weight)
    model_score     = _clamp(round(final_raw * 10))

    # Apply smoothing using the CURRENT confidence level
    _ALPHA_MAP = {"LOW": 0.20, "MEDIUM": 0.50, "HIGH": 0.80}
    current_conf = row.confidence.value if hasattr(row.confidence, "value") else row.confidence
    alpha = _ALPHA_MAP.get(current_conf, 0.20)
    projected_score = _clamp(round(alpha * model_score + (1 - alpha) * row.trust_score))

    projected_tier = score_to_tier(projected_score)

    # ── Calculate distance to next tier / confidence ──────────────────────────
    current_score = row.trust_score
    score_delta   = projected_score - current_score

    # Distance to next tier
    tier_thresholds = {"RESTRICTED": 400, "STANDARD": 600, "TRUSTED": 800}
    current_tier_str  = row.tier.value if hasattr(row.tier, "value") else row.tier
    next_tier_threshold = tier_thresholds.get(current_tier_str)
    points_to_next_tier = max(0, next_tier_threshold - projected_score) if next_tier_threshold else None

    return {
        "user_id":            user_id,
        "current_score":      current_score,
        "current_tier":       current_tier_str,
        "current_confidence": current_conf,
        "projected_score":    projected_score,
        "projected_tier":     projected_tier.value,
        "score_delta":        score_delta,
        "projected_dimensions": {k: round(v, 1) for k, v in dim_scores.items()},
        "points_to_next_tier": points_to_next_tier,
        "simulation_inputs": {
            "extra_completions":   ec,
            "extra_cancellations": en,
            "extra_returns":       er,
            "extra_payments":      ep,
        },
    }


# ── POST /trust/referral ──────────────────────────────────────────────────────

class ReferralRequest(BaseModel):
    referred_email: str


@router.post("/referral", status_code=201, summary="Claim referral reward")
def claim_referral(
    body: ReferralRequest,
    payload: dict = Depends(get_current_user_payload),
    db: Session = Depends(get_db),
):
    """Mark a referral as completed and update the referrer's trust score."""
    referrer_id = payload["sub"]
    referral = complete_referral(db, referrer_id, body.referred_email)
    profile = _build_profile(db, referrer_id)
    return {
        "message": "Referral completed successfully.",
        "trust_profile": profile,
    }


# ── POST /trust/events (admin) ────────────────────────────────────────────────

class ManualEventRequest(BaseModel):
    user_id:        str
    event_type:     str
    reference_id:   Optional[str] = None
    impact_summary: Optional[str] = None


@router.post("/events", status_code=201, summary="Fire a trust event (admin)")
def fire_trust_event(
    body: ManualEventRequest,
    payload: dict = Depends(require_role(UserRole.admin)),
    db: Session = Depends(get_db),
):
    """Manually fire a trust event for a user (admin only)."""
    try:
        event_type_enum = EventType(body.event_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown event type: {body.event_type}")

    record_event(
        db,
        body.user_id,
        event_type_enum,
        reference_id=body.reference_id,
        impact_summary=body.impact_summary,
    )
    update_features_for_users(db, [body.user_id])
    profile = trust_service.refresh_trust(db, body.user_id, event_type=body.event_type)
    return {"message": "Event fired and trust score updated.", "trust_score": profile.trust_score}


# ── POST /trust/refresh (admin) ───────────────────────────────────────────────

class RefreshRequest(BaseModel):
    user_id: str


@router.post("/refresh", summary="Manually recalculate trust score (admin)")
def refresh_trust_score(
    body: RefreshRequest,
    payload: dict = Depends(require_role(UserRole.admin)),
    db: Session = Depends(get_db),
):
    """Manually trigger a full trust recalculation for a user (admin only)."""
    profile = trust_service.refresh_trust(db, body.user_id)
    return {
        "message": "Trust score recalculated.",
        "user_id": body.user_id,
        "trust_score": profile.trust_score,
        "confidence":  profile.confidence.value if hasattr(profile.confidence, "value") else profile.confidence,
        "tier":        profile.tier.value if hasattr(profile.tier, "value") else profile.tier,
    }


# ── GET /trust/{user_id}/export ───────────────────────────────────────────────

@router.get("/{user_id}/export", summary="Export score history as CSV")
def export_score_history(
    user_id: str,
    payload: dict = Depends(get_current_user_payload),
    db: Session = Depends(get_db),
):
    """
    Download the user's full score history as a CSV file.
    Only the owner or an admin may download.
    """
    requester_id   = payload["sub"]
    requester_role = payload.get("role", "")

    if requester_id != user_id and requester_role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Access denied.")

    rows = (
        db.query(ScoreHistory)
        .filter(ScoreHistory.user_id == user_id)
        .order_by(ScoreHistory.created_at.asc())
        .all()
    )

    # Build CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["timestamp", "old_score", "new_score", "score_change", "event_type", "reason"])
    for r in rows:
        writer.writerow([
            r.created_at.isoformat() if r.created_at else "",
            r.old_score,
            r.new_score,
            r.score_change,
            r.event_type or "",
            r.reason or "",
        ])

    output.seek(0)
    filename = f"trustgrid_history_{user_id}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
