"""
TrustGrid Admin Analytics API.

Endpoints
---------
GET /admin/analytics          → aggregate TrustGrid statistics
GET /admin/users              → paginated user list with trust summary
GET /admin/trust-distribution → score distribution across all users

All endpoints require the 'admin' role.
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, case

from app.db.session import get_db
from app.core.dependencies import require_role
from app.models.user import User, UserRole
from app.models.trust import TrustScore, ScoreHistory, ConfidenceLevel, TrustTier
from app.models.marketplace import Order
from app.models.trust import TrustEvent

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
