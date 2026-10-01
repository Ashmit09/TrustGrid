"""
TrustGrid — Products API
GET    /products
POST   /products         (seller only)
GET    /products/{id}
"""
import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.product import Product
from app.models.user import User
from app.schemas.marketplace import ProductCreate, ProductRead
from app.services.auth_service import get_current_user, require_role

router = APIRouter()


@router.get("", response_model=List[ProductRead])
def list_products(db: Session = Depends(get_db)):
    return db.query(Product).filter(Product.is_active == True).all()


@router.post("", response_model=ProductRead, status_code=201)
def create_product(
    data: ProductCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("seller")),
):
    product = Product(
        product_id=f"PRD-{uuid.uuid4().hex[:8].upper()}",
        seller_id=current_user.user_id,
        title=data.title,
        description=data.description,
        price=data.price,
        stock=data.stock,
        category=data.category,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.get("/{product_id}", response_model=ProductRead)
def get_product(product_id: str, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.product_id == product_id).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found.")
    return product
