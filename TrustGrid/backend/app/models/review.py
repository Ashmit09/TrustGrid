"""
TrustGrid — Review ORM Model
Buyer submits a review; seller receives it (REVIEW_RECEIVED event).
"""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime
from app.db.database import Base


class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)
    review_id = Column(String(40), unique=True, nullable=False, index=True)
    order_id = Column(String(40), nullable=False, index=True)
    buyer_id = Column(String(20), nullable=False, index=True)
    seller_id = Column(String(20), nullable=False, index=True)
    rating = Column(Float, nullable=False)     # 1–5 star scale
    comment = Column(String(1000), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
