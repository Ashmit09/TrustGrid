"""
TrustGrid — Order ORM Model
"""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime
from app.db.database import Base


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(String(40), unique=True, nullable=False, index=True)
    buyer_id = Column(String(20), nullable=False, index=True)
    seller_id = Column(String(20), nullable=False, index=True)
    product_id = Column(String(40), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    total_amount = Column(Float, nullable=False)
    status = Column(String(30), nullable=False, default="PLACED")
    # PLACED | ACCEPTED | SHIPPED | DELIVERED | COMPLETED | CANCELLED | RETURN_REQUESTED | RETURNED
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
