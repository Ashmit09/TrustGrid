"""
TrustGrid — ScoreHistory ORM Model
Immutable log of every trust score change.
"""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime
from app.db.database import Base


class ScoreHistory(Base):
    __tablename__ = "score_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(20), nullable=False, index=True)
    old_score = Column(Integer, nullable=False)
    new_score = Column(Integer, nullable=False)
    score_change = Column(Integer, nullable=False)           # new - old (signed)
    reason = Column(String(255), nullable=True)              # short human explanation
    event_type = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
