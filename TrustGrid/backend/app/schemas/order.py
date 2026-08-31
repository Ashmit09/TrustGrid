"""
Pydantic schemas for orders, returns, reviews, referrals.
"""
from datetime import datetime
from typing import Optional
from decimal import Decimal
from pydantic import BaseModel, Field


# ── Orders ────────────────────────────────────────────────────────────────────

class OrderCreate(BaseModel):
    product_id: int
    quantity:   int = Field(1, ge=1, le=100)


class OrderOut(BaseModel):
    id:           int
    order_id:     str
    buyer_id:     str
    seller_id:    str
    product_id:   int
    quantity:     int
    unit_price:   Decimal
    total_amount: Decimal
    status:       str
    created_at:   datetime
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class OrderDetailOut(OrderOut):
    """Order with nested product title and payment status."""
    product_title:   Optional[str] = None
    payment_status:  Optional[str] = None


# ── Returns ───────────────────────────────────────────────────────────────────

class ReturnCreate(BaseModel):
    reason: Optional[str] = Field(None, max_length=500)


class ReturnOut(BaseModel):
    id:         int
    order_id:   str
    buyer_id:   str
    seller_id:  str
    reason:     Optional[str]
    status:     str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Reviews ───────────────────────────────────────────────────────────────────

class ReviewCreate(BaseModel):
    rating:  int     = Field(..., ge=1, le=5)
    comment: Optional[str] = Field(None, max_length=1000)


class ReviewOut(BaseModel):
    id:          int
    order_id:    str
    reviewer_id: str
    seller_id:   str
    rating:      int
    comment:     Optional[str]
    created_at:  datetime

    model_config = {"from_attributes": True}


# ── Referrals ─────────────────────────────────────────────────────────────────

class ReferralCreate(BaseModel):
    referred_email: str


class ReferralOut(BaseModel):
    id:          int
    referrer_id: str
    referred_id: str
    status:      str
    created_at:  datetime

    model_config = {"from_attributes": True}
