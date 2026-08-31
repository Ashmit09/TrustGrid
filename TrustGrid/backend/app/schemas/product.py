"""
Pydantic schemas for products.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from decimal import Decimal


class ProductCreate(BaseModel):
    title:       str     = Field(..., min_length=2, max_length=255)
    description: Optional[str] = None
    price:       Decimal = Field(..., gt=0, decimal_places=2)
    stock:       int     = Field(..., ge=0)
    category:    Optional[str] = Field(None, max_length=100)
    image_url:   Optional[str] = Field(None, max_length=500)


class ProductUpdate(BaseModel):
    title:       Optional[str]     = Field(None, min_length=2, max_length=255)
    description: Optional[str]     = None
    price:       Optional[Decimal] = Field(None, gt=0, decimal_places=2)
    stock:       Optional[int]     = Field(None, ge=0)
    category:    Optional[str]     = Field(None, max_length=100)
    image_url:   Optional[str]     = Field(None, max_length=500)
    is_active:   Optional[bool]    = None


class ProductOut(BaseModel):
    id:          int
    seller_id:   str
    title:       str
    description: Optional[str]
    price:       Decimal
    stock:       int
    category:    Optional[str]
    image_url:   Optional[str]
    is_active:   bool
    created_at:  datetime

    model_config = {"from_attributes": True}
