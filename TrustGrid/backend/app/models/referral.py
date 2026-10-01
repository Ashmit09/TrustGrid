"""
TrustGrid — Referral ORM Model
Tracks successful buyer referrals (REFERRAL_COMPLETED event).
"""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime
from app.db.database import Base


class Referral(Base):
    __tablename__ = "referrals"

    id = Column(Integer, primary_key=True, index=True)
    referral_id = Column(String(40), unique=True, nullable=False, index=True)
    referrer_id = Column(String(20), nullable=False, index=True)   # BUY-xxxxx who referred
    referred_id = Column(String(20), nullable=False, index=True)   # new user who signed up
    status = Column(String(20), nullable=False, default="PENDING") # PENDING | COMPLETED
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime(timezone=True), nullable=True)
