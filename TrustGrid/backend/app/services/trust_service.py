"""
TrustGrid Trust Service — orchestration layer.

After any marketplace event, call:

    trust_service.refresh_trust(db, user_id)

This single function:
  1. Reads the latest committed feature vector.
  2. Calls the trust engine to compute a new score.
  3. Calls the privilege engine to update benefits.
  4. Returns the updated TrustScore row.

It is the ONLY entry point for score recalculation.
Service layers (order_service, etc.) call this after committing events.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models.trust import TrustScore
from app.models.user import User, UserRole
from app.trustgrid.feature_engine import get_feature_vector
from app.trustgrid.trust_engine import recalculate_trust_score
from app.trustgrid.privilege_engine import recalculate_privileges
from app.trustgrid.explanation_service import describe_score_change


def refresh_trust(
    db: Session,
    user_id: str,
    event_type: Optional[str] = None,
    reason: Optional[str] = None,
) -> TrustScore:
    """
    Full TrustGrid recalculation pipeline for one user.

    Parameters
    ----------
    db         : database session (must be after event + feature commits)
    user_id    : BUY-xxxxx or SEL-xxxxx
    event_type : the event that triggered this recalculation (for history record)
    reason     : optional override for the score-history reason text

    Returns
    -------
    Updated TrustScore ORM row.
    """
    # 1. Load user (needed for role + account age)
    user: Optional[User] = db.query(User).filter(User.user_id == user_id).first()
    if user is None:
        raise ValueError(f"User not found: {user_id}")

    role: UserRole = user.role
    account_created_at: Optional[datetime] = user.created_at

    # 2. Get latest committed features
    features = get_feature_vector(db, user_id)

    # 3. Build a natural-language reason if none provided
    if reason is None and event_type is not None:
        reason = describe_score_change(0, event_type)

    # 4. Recalculate trust score (also persists score + history)
    trust_row = recalculate_trust_score(
        db=db,
        user_id=user_id,
        role=role,
        features=features,
        account_created_at=account_created_at,
        event_type=event_type,
        reason=reason,
    )

    # 5. Recalculate privileges
    recalculate_privileges(
        db=db,
        user_id=user_id,
        role=role,
        trust_score=trust_row.trust_score,
        confidence=trust_row.confidence,
    )

    return trust_row


def get_trust_profile(db: Session, user_id: str) -> Optional[TrustScore]:
    """Return the current TrustScore row (or None if user not found)."""
    return db.query(TrustScore).filter(TrustScore.user_id == user_id).first()
