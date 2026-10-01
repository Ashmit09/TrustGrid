"""
TrustGrid — TrustEvent ORM Model
Every marketplace action that affects trust is stored here.
"""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, JSON
from app.db.database import Base


class TrustEvent(Base):
    __tablename__ = "trust_events"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String(40), unique=True, nullable=False, index=True)   # UUID
    user_id = Column(String(20), nullable=False, index=True)
    role = Column(String(20), nullable=False)                                # buyer | seller
    event_type = Column(String(50), nullable=False)                          # e.g. ORDER_COMPLETED
    transaction_id = Column(String(40), nullable=True)                       # linked order/payment
    metadata_ = Column("metadata", JSON, nullable=True)                      # flexible payload
    impact_summary = Column(String(255), nullable=True)                      # human label
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
