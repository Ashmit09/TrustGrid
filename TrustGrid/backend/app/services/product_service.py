"""
Product service — CRUD operations.
"""
from typing import Optional, List
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.product import Product
from app.schemas.product import ProductCreate, ProductUpdate
from app.trustgrid.event_service import record_event, update_features_for_users
from app.trustgrid.event_types import EventType


def list_products(
    db: Session,
    category: Optional[str] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 40,
) -> List[Product]:
    q = db.query(Product).filter(Product.is_active == True)
    if category:
        q = q.filter(Product.category.ilike(f"%{category}%"))
    if search:
        q = q.filter(Product.title.ilike(f"%{search}%"))
    return q.order_by(Product.created_at.desc()).offset(skip).limit(limit).all()


def get_product(db: Session, product_id: int) -> Product:
    p = db.query(Product).filter(Product.id == product_id).first()
    if not p:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found.")
    return p


def create_product(db: Session, seller_id: str, data: ProductCreate) -> Product:
    product = Product(
        seller_id=seller_id,
        title=data.title,
        description=data.description,
        price=data.price,
        stock=data.stock,
        category=data.category,
        image_url=data.image_url,
    )
    db.add(product)
    db.commit()
    db.refresh(product)

    record_event(db, seller_id, EventType.PRODUCT_LISTED,
                 reference_id=str(product.id),
                 impact_summary="Listed a new product")
    update_features_for_users(db, [seller_id])

    return product


def update_product(db: Session, product_id: int, seller_id: str, data: ProductUpdate) -> Product:
    product = get_product(db, product_id)
    if product.seller_id != seller_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your product.")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
    db.commit()
    db.refresh(product)
    return product


def get_seller_products(db: Session, seller_id: str) -> List[Product]:
    return (
        db.query(Product)
        .filter(Product.seller_id == seller_id)
        .order_by(Product.created_at.desc())
        .all()
    )
