"""
TrustGrid — Payment ORM Model
Simulated payment outcomes only; no real card credentials are stored.
"""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime
from app.db.database import Base


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    payment_id = Column(String(40), unique=True, nullable=False, index=True)
    order_id = Column(String(40), nullable=False, index=True)
    buyer_id = Column(String(20), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    status = Column(String(20), nullable=False)   # SUCCESS | FAILED | ABANDONED
    method = Column(String(30), nullable=True)    # COD | CARD_SIMULATED | WALLET
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
