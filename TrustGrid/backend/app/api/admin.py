"""
TrustGrid Admin Analytics API.

Endpoints
---------
GET  /admin/analytics          → aggregate TrustGrid statistics
GET  /admin/users              → paginated user list with trust summary
GET  /admin/trust-distribution → score distribution across all users
GET  /admin/anomalies          → list open anomaly flags
POST /admin/anomalies/scan     → trigger anomaly scan now
PATCH /admin/anomalies/{flag_id}/resolve → mark a flag resolved

All endpoints require the 'admin' role.
"""
from typing import Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.session import get_db
from app.core.dependencies import require_role
from app.models.user import User, UserRole
from app.models.trust import TrustScore, ScoreHistory, ConfidenceLevel, TrustTier, AnomalyFlag
from app.models.marketplace import Order
from app.models.trust import TrustEvent
from app.services.anomaly_service import run_anomaly_scan

router = APIRouter()


@router.get("/analytics", summary="Aggregate TrustGrid analytics")
def get_analytics(
    payload: dict = Depends(require_role(UserRole.admin)),
    db: Session = Depends(get_db),
):
    """Return aggregate statistics across all users and trust scores."""

    total_buyers  = db.query(func.count(User.id)).filter(User.role == UserRole.buyer).scalar() or 0
    total_sellers = db.query(func.count(User.id)).filter(User.role == UserRole.seller).scalar() or 0

    # Average scores
    buyer_scores  = db.query(TrustScore.trust_score).join(User, TrustScore.user_id == User.user_id).filter(User.role == UserRole.buyer).all()
    seller_scores = db.query(TrustScore.trust_score).join(User, TrustScore.user_id == User.user_id).filter(User.role == UserRole.seller).all()

    avg_buyer_score  = round(sum(s[0] for s in buyer_scores)  / len(buyer_scores),  1) if buyer_scores  else 0
    avg_seller_score = round(sum(s[0] for s in seller_scores) / len(seller_scores), 1) if seller_scores else 0

    # Tier distribution (buyers)
    buyer_tiers = {}
    for tier in TrustTier:
        cnt = db.query(func.count(TrustScore.id)).join(User, TrustScore.user_id == User.user_id).filter(
            User.role == UserRole.buyer,
            TrustScore.tier == tier,
        ).scalar() or 0
        buyer_tiers[tier.value] = cnt

    # Tier distribution (sellers)
    seller_tiers = {}
    for tier in TrustTier:
        cnt = db.query(func.count(TrustScore.id)).join(User, TrustScore.user_id == User.user_id).filter(
            User.role == UserRole.seller,
            TrustScore.tier == tier,
        ).scalar() or 0
        seller_tiers[tier.value] = cnt

    # Confidence distribution
    conf_dist = {}
    for conf in ConfidenceLevel:
        cnt = db.query(func.count(TrustScore.id)).filter(TrustScore.confidence == conf).scalar() or 0
        conf_dist[conf.value] = cnt

    # Total events
    total_events = db.query(func.count(TrustEvent.id)).scalar() or 0
    total_orders = db.query(func.count(Order.id)).scalar() or 0

    # Recent score changes (last 10)
    recent_changes = (
        db.query(ScoreHistory)
        .order_by(ScoreHistory.created_at.desc())
        .limit(10)
        .all()
    )
    recent_changes_out = [
        {
            "user_id":      r.user_id,
            "score_change": r.score_change,
            "new_score":    r.new_score,
            "reason":       r.reason,
            "created_at":   r.created_at.isoformat() if r.created_at else None,
        }
        for r in recent_changes
    ]

    # Most common event types
    event_counts = (
        db.query(TrustEvent.event_type, func.count(TrustEvent.id).label("cnt"))
        .group_by(TrustEvent.event_type)
        .order_by(func.count(TrustEvent.id).desc())
        .limit(8)
        .all()
    )
    top_events = [{"event_type": e[0], "count": e[1]} for e in event_counts]

    return {
        "totals": {
            "buyers":        total_buyers,
            "sellers":       total_sellers,
            "total_users":   total_buyers + total_sellers,
            "total_events":  total_events,
            "total_orders":  total_orders,
        },
        "averages": {
            "avg_buyer_score":  avg_buyer_score,
            "avg_seller_score": avg_seller_score,
        },
        "buyer_tiers":      buyer_tiers,
        "seller_tiers":     seller_tiers,
        "confidence_dist":  conf_dist,
        "recent_changes":   recent_changes_out,
        "top_event_types":  top_events,
    }


@router.get("/users", summary="List all users with trust summary")
def list_users(
    role:   Optional[str] = Query(default=None, description="Filter by role: buyer | seller"),
    limit:  int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    payload: dict = Depends(require_role(UserRole.admin)),
    db: Session = Depends(get_db),
):
    """Return paginated list of users with their trust summary."""
    q = db.query(User)
    if role:
        q = q.filter(User.role == role)
    total = q.count()
    users = q.order_by(User.created_at.desc()).offset(offset).limit(limit).all()

    result = []
    for u in users:
        ts = db.query(TrustScore).filter(TrustScore.user_id == u.user_id).first()
        result.append({
            "user_id":     u.user_id,
            "name":        u.name,
            "email":       u.email,
            "role":        u.role.value,
            "created_at":  u.created_at.isoformat() if u.created_at else None,
            "trust_score": ts.trust_score  if ts else 700,
            "confidence":  ts.confidence.value if ts else "LOW",
            "tier":        ts.tier.value if ts else "TRUSTED",
        })

    return {"total": total, "users": result, "offset": offset, "limit": limit}


@router.get("/trust-distribution", summary="Score distribution histogram")
def get_trust_distribution(
    payload: dict = Depends(require_role(UserRole.admin)),
    db: Session = Depends(get_db),
):
    """Return score distribution in 100-point buckets for buyers and sellers."""
    buckets = [(i, i + 99) for i in range(0, 1000, 100)]
    labels  = [f"{lo}–{hi}" for lo, hi in buckets]

    def bucket_counts(role: UserRole):
        counts = []
        for lo, hi in buckets:
            cnt = (
                db.query(func.count(TrustScore.id))
                .join(User, TrustScore.user_id == User.user_id)
                .filter(
                    User.role == role,
                    TrustScore.trust_score >= lo,
                    TrustScore.trust_score <= hi,
                )
                .scalar() or 0
            )
            counts.append(cnt)
        return counts

    return {
        "labels":  labels,
        "buyers":  bucket_counts(UserRole.buyer),
        "sellers": bucket_counts(UserRole.seller),
    }


def _flag_out(flag: AnomalyFlag) -> dict:
    return {
        "flag_id":      flag.flag_id,
        "user_id":      flag.user_id,
        "flag_type":    flag.flag_type,
        "severity":     flag.severity,
        "description":  flag.description,
        "score_before": flag.score_before,
        "score_after":  flag.score_after,
        "resolved":     bool(flag.resolved),
        "created_at":   flag.created_at.isoformat() if flag.created_at else None,
        "resolved_at":  flag.resolved_at.isoformat() if flag.resolved_at else None,
    }


@router.get("/anomalies", summary="List anomaly flags")
def list_anomalies(
    resolved:  Optional[bool] = Query(default=None, description="Filter by resolved status"),
    severity:  Optional[str]  = Query(default=None, description="Filter by severity: LOW | MEDIUM | HIGH"),
    limit:     int = Query(default=50, ge=1, le=200),
    offset:    int = Query(default=0, ge=0),
    payload: dict = Depends(require_role(UserRole.admin)),
    db: Session = Depends(get_db),
):
    """Return anomaly flags, newest first.  Use ?resolved=false to see only open alerts."""
    q = db.query(AnomalyFlag)
    if resolved is not None:
        q = q.filter(AnomalyFlag.resolved == (1 if resolved else 0))
    if severity:
        q = q.filter(AnomalyFlag.severity == severity.upper())
    total = q.count()
    flags = q.order_by(AnomalyFlag.created_at.desc()).offset(offset).limit(limit).all()
    return {
        "total":   total,
        "offset":  offset,
        "limit":   limit,
        "anomalies": [_flag_out(f) for f in flags],
    }


@router.post("/anomalies/scan", status_code=200, summary="Trigger anomaly scan")
def trigger_scan(
    payload: dict = Depends(require_role(UserRole.admin)),
    db: Session = Depends(get_db),
):
    """Run the anomaly detection pass immediately and return any newly created flags."""
    new_flags = run_anomaly_scan(db)
    return {
        "new_flags_created": len(new_flags),
        "flags": [_flag_out(f) for f in new_flags],
    }


@router.patch("/anomalies/{flag_id}/resolve", summary="Resolve an anomaly flag")
def resolve_anomaly(
    flag_id: str,
    payload: dict = Depends(require_role(UserRole.admin)),
    db: Session = Depends(get_db),
):
    """Mark an anomaly flag as resolved."""
    flag = db.query(AnomalyFlag).filter(AnomalyFlag.flag_id == flag_id).first()
    if not flag:
        raise HTTPException(status_code=404, detail="Flag not found.")
    if flag.resolved:
        raise HTTPException(status_code=409, detail="Flag is already resolved.")
    flag.resolved    = 1
    flag.resolved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(flag)
    return _flag_out(flag)
