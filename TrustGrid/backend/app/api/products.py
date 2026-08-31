"""
Product routes:
  GET  /products             — public list
  GET  /products/{id}        — public detail
  POST /products             — seller creates
  PUT  /products/{id}        — seller updates
  GET  /products/my          — seller's own products
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.product import ProductCreate, ProductUpdate, ProductOut
from app.services.product_service import (
    list_products, get_product, create_product, update_product, get_seller_products
)
from app.core.dependencies import get_current_user_payload, require_role

router = APIRouter()


@router.get("", response_model=List[ProductOut], summary="List all active products")
def list_all_products(
    category: Optional[str] = Query(None),
    search:   Optional[str] = Query(None),
    skip:     int           = Query(0, ge=0),
    limit:    int           = Query(40, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return list_products(db, category=category, search=search, skip=skip, limit=limit)


@router.get("/my", response_model=List[ProductOut], summary="Seller's own products")
def my_products(
    payload: dict = Depends(require_role("seller", "admin")),
    db: Session   = Depends(get_db),
):
    return get_seller_products(db, payload["sub"])


@router.get("/{product_id}", response_model=ProductOut, summary="Get product detail")
def product_detail(product_id: int, db: Session = Depends(get_db)):
    return get_product(db, product_id)


@router.post("", response_model=ProductOut, status_code=201, summary="Create product (seller)")
def create(
    data:    ProductCreate,
    payload: dict       = Depends(require_role("seller")),
    db:      Session    = Depends(get_db),
):
    return create_product(db, seller_id=payload["sub"], data=data)


@router.put("/{product_id}", response_model=ProductOut, summary="Update product (seller)")
def update(
    product_id: int,
    data:       ProductUpdate,
    payload:    dict    = Depends(require_role("seller")),
    db:         Session = Depends(get_db),
):
    return update_product(db, product_id=product_id, seller_id=payload["sub"], data=data)
