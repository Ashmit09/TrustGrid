"""
User ORM model.
user_id is the primary logical identifier (BUY-10001 / SEL-20001).
email is used only for authentication.
"""
import enum
from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, Enum, DateTime
from sqlalchemy.orm import relationship

from app.db.base import Base


class UserRole(str, enum.Enum):
    buyer  = "buyer"
    seller = "seller"
    admin  = "admin"


class User(Base):
    __tablename__ = "users"

    id            = Column(Integer, primary_key=True, index=True)
    user_id       = Column(String(20), unique=True, nullable=False, index=True)
    name          = Column(String(120), nullable=False)
    email         = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role          = Column(Enum(UserRole), nullable=False, default=UserRole.buyer)
    created_at    = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at    = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    # Relationships (populated in later phases)
    trust_score     = relationship("TrustScore",       back_populates="user", uselist=False)
    score_history   = relationship("ScoreHistory",     back_populates="user")
    trust_events    = relationship("TrustEvent",       back_populates="user")
    behavior_features = relationship("BehaviorFeatures", back_populates="user", uselist=False)
    privileges      = relationship("Privilege",        back_populates="user")
