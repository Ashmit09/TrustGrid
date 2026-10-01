"""
TrustGrid — Return ORM Model
Tracks return requests and their resolution status.
"""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from app.db.database import Base


class Return(Base):
    __tablename__ = "returns"

    id = Column(Integer, primary_key=True, index=True)
    return_id = Column(String(40), unique=True, nullable=False, index=True)
    order_id = Column(String(40), nullable=False, index=True)
    buyer_id = Column(String(20), nullable=False, index=True)
    seller_id = Column(String(20), nullable=False, index=True)
    reason = Column(String(255), nullable=True)
    is_problematic = Column(Boolean, default=False)   # seller-marked or policy-flagged
    status = Column(String(30), nullable=False, default="REQUESTED")
    # REQUESTED | ACCEPTED | REJECTED | RESOLVED
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    resolved_at = Column(DateTime(timezone=True), nullable=True)
