"""
Order, Payment, Return, Review, Referral ORM models.
"""
import enum
from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Text, Numeric, DateTime, ForeignKey, Enum
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class OrderStatus(str, enum.Enum):
    pending    = "pending"
    paid       = "paid"
    shipped    = "shipped"
    delivered  = "delivered"
    completed  = "completed"
    cancelled  = "cancelled"
    returned   = "returned"


class PaymentStatus(str, enum.Enum):
    success = "success"
    failed  = "failed"


class ReturnStatus(str, enum.Enum):
    pending  = "pending"
    resolved = "resolved"
    rejected = "rejected"


class Order(Base):
    __tablename__ = "orders"

    id           = Column(Integer, primary_key=True, index=True)
    order_id     = Column(String(30), unique=True, nullable=False, index=True)
    buyer_id     = Column(String(20), ForeignKey("users.user_id"), nullable=False, index=True)
    seller_id    = Column(String(20), ForeignKey("users.user_id"), nullable=False, index=True)
    product_id   = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity     = Column(Integer, default=1, nullable=False)
    unit_price   = Column(Numeric(10, 2), nullable=False)
    total_amount = Column(Numeric(10, 2), nullable=False)
    status       = Column(Enum(OrderStatus), default=OrderStatus.pending, nullable=False)
    created_at   = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime(timezone=True), nullable=True)

    buyer   = relationship("User", foreign_keys=[buyer_id])
    seller  = relationship("User", foreign_keys=[seller_id])
    product = relationship("Product", back_populates="order_items")
    payment = relationship("Payment", back_populates="order", uselist=False)
    review  = relationship("Review",  back_populates="order", uselist=False)
    return_ = relationship("Return",  back_populates="order", uselist=False)


class Payment(Base):
    __tablename__ = "payments"

    id         = Column(Integer, primary_key=True, index=True)
    order_id   = Column(String(30), ForeignKey("orders.order_id"), nullable=False, index=True)
    buyer_id   = Column(String(20), ForeignKey("users.user_id"), nullable=False, index=True)
    amount     = Column(Numeric(10, 2), nullable=False)
    status     = Column(Enum(PaymentStatus), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    order = relationship("Order", back_populates="payment")


class Return(Base):
    __tablename__ = "returns"

    id          = Column(Integer, primary_key=True, index=True)
    order_id    = Column(String(30), ForeignKey("orders.order_id"), nullable=False, index=True)
    buyer_id    = Column(String(20), ForeignKey("users.user_id"), nullable=False, index=True)
    seller_id   = Column(String(20), ForeignKey("users.user_id"), nullable=False, index=True)
    reason      = Column(Text, nullable=True)
    status      = Column(Enum(ReturnStatus), default=ReturnStatus.pending, nullable=False)
    created_at  = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    order = relationship("Order", back_populates="return_")


class Review(Base):
    __tablename__ = "reviews"

    id          = Column(Integer, primary_key=True, index=True)
    order_id    = Column(String(30), ForeignKey("orders.order_id"), nullable=False, index=True)
    reviewer_id = Column(String(20), ForeignKey("users.user_id"), nullable=False, index=True)
    seller_id   = Column(String(20), ForeignKey("users.user_id"), nullable=False, index=True)
    rating      = Column(Integer, nullable=False)   # 1–5
    comment     = Column(Text, nullable=True)
    created_at  = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    order = relationship("Order", back_populates="review")


class Referral(Base):
    __tablename__ = "referrals"

    id          = Column(Integer, primary_key=True, index=True)
    referrer_id = Column(String(20), ForeignKey("users.user_id"), nullable=False, index=True)
    referred_id = Column(String(20), ForeignKey("users.user_id"), nullable=False, index=True)
    status      = Column(String(20), default="pending", nullable=False)
    created_at  = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
