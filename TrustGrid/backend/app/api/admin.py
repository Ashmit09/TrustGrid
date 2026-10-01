"""
TrustGrid — Admin API
GET /admin/analytics
GET /admin/users
GET /admin/trust-distribution
"""
from typing import List, Dict
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User
from app.models.trust_score import TrustScore
from app.models.score_history import ScoreHistory
from app.schemas.auth import UserRead
from app.services.auth_service import require_role

router = APIRouter()


@router.get("/users", response_model=List[UserRead])
def list_all_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    return db.query(User).all()


@router.get("/trust-distribution")
def trust_distribution(
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    rows = db.query(TrustScore).all()
    dist: Dict[str, int] = {"RESTRICTED": 0, "STANDARD": 0, "TRUSTED": 0, "ELITE": 0}
    confidence_dist: Dict[str, int] = {"LOW": 0, "MEDIUM": 0, "HIGH": 0}
    for r in rows:
        dist[r.tier] = dist.get(r.tier, 0) + 1
        confidence_dist[r.confidence] = confidence_dist.get(r.confidence, 0) + 1
    avg_score = (
        db.query(func.avg(TrustScore.trust_score)).scalar() or 0
    )
    return {
        "total_users": len(rows),
        "tier_distribution": dist,
        "confidence_distribution": confidence_dist,
        "average_trust_score": round(float(avg_score), 1),
    }


@router.get("/analytics")
def admin_analytics(
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    total_users = db.query(User).count()
    total_buyers = db.query(User).filter(User.role == "buyer").count()
    total_sellers = db.query(User).filter(User.role == "seller").count()
    total_events = db.query(ScoreHistory).count()
    return {
        "total_users":   total_users,
        "total_buyers":  total_buyers,
        "total_sellers": total_sellers,
        "total_score_changes": total_events,
    }
