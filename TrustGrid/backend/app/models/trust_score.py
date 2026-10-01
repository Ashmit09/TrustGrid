"""
TrustGrid — TrustScore ORM Model
One row per user — the live trust state.
"""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from app.db.database import Base


class TrustScore(Base):
    __tablename__ = "trust_scores"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(20), ForeignKey("users.user_id"), unique=True, nullable=False, index=True)
    trust_score = Column(Integer, nullable=False, default=700)       # 0–1000
    confidence = Column(String(10), nullable=False, default="LOW")   # LOW/MEDIUM/HIGH
    tier = Column(String(20), nullable=False, default="TRUSTED")     # RESTRICTED/STANDARD/TRUSTED/ELITE
    last_updated = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
