"""
User service — business logic for user registration and lookup.
Also initialises the TrustGrid records (TrustScore, BehaviorFeatures)
for every new user.
"""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.user import User, UserRole
from app.models.trust import TrustScore, BehaviorFeatures, ConfidenceLevel, TrustTier
from app.core.security import hash_password
from app.core.config import settings
from app.utils.user_id import generate_user_id


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email.lower()).first()


def get_user_by_id(db: Session, user_id: str) -> Optional[User]:
    return db.query(User).filter(User.user_id == user_id).first()


def create_user(db: Session, name: str, email: str, password: str, role: str) -> User:
    """
    Register a new user.
    1. Checks for duplicate email.
    2. Generates unique user_id.
    3. Creates User row.
    4. Creates initial TrustScore (700 / LOW / TRUSTED).
    5. Creates empty BehaviorFeatures row.
    """
    # 1. Duplicate check
    if get_user_by_email(db, email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    user_role = UserRole(role)

    # 2. Generate user ID
    user_id = generate_user_id(db, user_role)

    # 3. Create user
    user = User(
        user_id=user_id,
        name=name.strip(),
        email=email.lower(),
        password_hash=hash_password(password),
        role=user_role,
    )
    db.add(user)
    db.flush()   # flush so user_id FK is available below

    # 4. Initial TrustScore — every new user starts at 700 / LOW / TRUSTED
    initial_dim_scores = _initial_dim_scores(user_role)
    trust = TrustScore(
        user_id=user_id,
        trust_score=settings.INITIAL_TRUST_SCORE,
        confidence=ConfidenceLevel.LOW,
        tier=TrustTier.TRUSTED,
        dim_scores=initial_dim_scores,
        last_updated=datetime.now(timezone.utc),
    )
    db.add(trust)

    # 5. BehaviorFeatures row — initialised with neutral defaults
    #    Rates default to 1.0 (no evidence → assume reliable)
    features = BehaviorFeatures(
        user_id=user_id,
        order_completion_rate=1.0,
        return_rate=0.0,
        payment_success_rate=1.0,
        cancellation_rate=0.0,
        fulfillment_rate=1.0,
        late_delivery_rate=0.0,
        return_response_rate=1.0,
        avg_rating_received=0.0,
        decayed_event_weight=0.0,
    )
    db.add(features)

    db.commit()
    db.refresh(user)
    return user


def _initial_dim_scores(role: UserRole) -> dict:
    """
    Return neutral starting dimension scores (70/100 each).
    These reflect the 700/1000 starting score (70 × 10 = 700).
    They will be overwritten once real behavioral data exists.
    """
    if role == UserRole.buyer:
        return {
            "order_reliability":      70.0,
            "return_behaviour":       70.0,
            "payment_reliability":    70.0,
            "cancellation_behaviour": 70.0,
            "platform_engagement":    70.0,
        }
    else:
        return {
            "order_fulfillment":       70.0,
            "delivery_performance":    70.0,
            "customer_satisfaction":   70.0,
            "return_dispute_handling": 70.0,
            "platform_reliability":    70.0,
        }
