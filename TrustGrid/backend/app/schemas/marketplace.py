"""
TrustGrid — Pydantic Schemas: Products, Orders, Payments, Returns, Reviews
"""
from pydantic import BaseModel, Field
from typing import Optional, Literal


# ── Products ──────────────────────────────────────────────────────────────────

class ProductCreate(BaseModel):
    title: str
    description: Optional[str] = None
    price: float = Field(..., gt=0)
    stock: int = Field(..., ge=0)
    category: Optional[str] = None


class ProductRead(BaseModel):
    product_id: str
    seller_id: str
    title: str
    description: Optional[str]
    price: float
    stock: int
    category: Optional[str]
    is_active: bool

    model_config = {"from_attributes": True}


# ── Orders ────────────────────────────────────────────────────────────────────

class OrderCreate(BaseModel):
    product_id: str
    quantity: int = Field(1, ge=1)


class OrderRead(BaseModel):
    order_id: str
    buyer_id: str
    seller_id: str
    product_id: str
    quantity: int
    total_amount: float
    status: str

    model_config = {"from_attributes": True}


# ── Payments ──────────────────────────────────────────────────────────────────

class PaymentCreate(BaseModel):
    order_id: str
    method: Literal["COD", "CARD_SIMULATED", "WALLET"] = "CARD_SIMULATED"


class PaymentRead(BaseModel):
    payment_id: str
    order_id: str
    buyer_id: str
    amount: float
    status: str
    method: Optional[str]

    model_config = {"from_attributes": True}


# ── Returns ───────────────────────────────────────────────────────────────────

class ReturnCreate(BaseModel):
    reason: Optional[str] = None


class ReturnRead(BaseModel):
    return_id: str
    order_id: str
    buyer_id: str
    seller_id: str
    reason: Optional[str]
    is_problematic: bool
    status: str

    model_config = {"from_attributes": True}


# ── Reviews ───────────────────────────────────────────────────────────────────

class ReviewCreate(BaseModel):
    rating: float = Field(..., ge=1.0, le=5.0)
    comment: Optional[str] = None


class ReviewRead(BaseModel):
    review_id: str
    order_id: str
    buyer_id: str
    seller_id: str
    rating: float
    comment: Optional[str]

    model_config = {"from_attributes": True}
