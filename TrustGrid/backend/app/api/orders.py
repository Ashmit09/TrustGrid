"""
TrustGrid — Orders API
POST /orders                   (buyer places order)
GET  /orders                   (buyer or seller sees their orders)
POST /orders/{id}/cancel       (buyer or seller cancels)
POST /orders/{id}/pay          (buyer pays → triggers PAYMENT_SUCCESS/FAILED)
POST /orders/{id}/return       (buyer requests return)
POST /orders/{id}/review       (buyer submits review after delivery)
POST /orders/{id}/ship         (seller ships)
POST /orders/{id}/deliver      (seller marks delivered)
POST /orders/{id}/fulfill      (seller fulfills / accepts)
"""
import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.order import Order
from app.models.product import Product
from app.models.payment import Payment
from app.models.return_model import Return
from app.models.review import Review
from app.models.user import User
from app.schemas.marketplace import (
    OrderCreate, OrderRead,
    PaymentCreate, PaymentRead,
    ReturnCreate, ReturnRead,
    ReviewCreate, ReviewRead,
)
from app.services.auth_service import get_current_user
from app.services.event_service import emit_event

router = APIRouter()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_order_or_404(db: Session, order_id: str) -> Order:
    order = db.query(Order).filter(Order.order_id == order_id).first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
    return order


# ── Place Order ───────────────────────────────────────────────────────────────

@router.post("", response_model=OrderRead, status_code=201)
def place_order(
    data: OrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "buyer":
        raise HTTPException(status_code=403, detail="Only buyers can place orders.")
    product = db.query(Product).filter(Product.product_id == data.product_id, Product.is_active == True).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")
    if product.stock < data.quantity:
        raise HTTPException(status_code=400, detail="Insufficient stock.")

    order = Order(
        order_id=f"ORD-{uuid.uuid4().hex[:8].upper()}",
        buyer_id=current_user.user_id,
        seller_id=product.seller_id,
        product_id=data.product_id,
        quantity=data.quantity,
        total_amount=round(product.price * data.quantity, 2),
        status="PLACED",
    )
    product.stock -= data.quantity
    db.add(order)
    db.commit()
    db.refresh(order)
    # Emit trust event for buyer
    emit_event(db, user_id=current_user.user_id, role="buyer",
               event_type="ORDER_PLACED", transaction_id=order.order_id)
    # Emit for seller
    emit_event(db, user_id=order.seller_id, role="seller",
               event_type="ORDER_ACCEPTED", transaction_id=order.order_id)
    return order


# ── List Orders ────────────────────────────────────────────────────────────────

@router.get("", response_model=List[OrderRead])
def list_orders(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role == "buyer":
        return db.query(Order).filter(Order.buyer_id == current_user.user_id).all()
    elif current_user.role == "seller":
        return db.query(Order).filter(Order.seller_id == current_user.user_id).all()
    else:  # admin
        return db.query(Order).all()


# ── Cancel Order ───────────────────────────────────────────────────────────────

@router.post("/{order_id}/cancel", response_model=OrderRead)
def cancel_order(
    order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = _get_order_or_404(db, order_id)
    if order.status not in ("PLACED", "ACCEPTED"):
        raise HTTPException(status_code=400, detail=f"Cannot cancel order in status {order.status}.")
    if current_user.role == "buyer" and order.buyer_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied.")
    if current_user.role == "seller" and order.seller_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied.")

    order.status = "CANCELLED"
    db.commit()
    db.refresh(order)
    # Buyer cancels → ORDER_CANCELLED; seller cancels → SELLER_CANCELLED
    if current_user.role == "buyer":
        emit_event(db, user_id=current_user.user_id, role="buyer",
                   event_type="ORDER_CANCELLED", transaction_id=order.order_id)
    else:
        emit_event(db, user_id=current_user.user_id, role="seller",
                   event_type="SELLER_CANCELLED", transaction_id=order.order_id)
    return order


# ── Seller: Fulfill / Accept ───────────────────────────────────────────────────

@router.post("/{order_id}/fulfill", response_model=OrderRead)
def fulfill_order(
    order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "seller":
        raise HTTPException(status_code=403, detail="Only sellers can fulfill orders.")
    order = _get_order_or_404(db, order_id)
    if order.seller_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied.")
    if order.status != "PLACED":
        raise HTTPException(status_code=400, detail=f"Cannot fulfill order in status {order.status}.")
    order.status = "ACCEPTED"
    db.commit()
    db.refresh(order)
    return order


# ── Seller: Ship ───────────────────────────────────────────────────────────────

@router.post("/{order_id}/ship", response_model=OrderRead)
def ship_order(
    order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "seller":
        raise HTTPException(status_code=403, detail="Only sellers can ship orders.")
    order = _get_order_or_404(db, order_id)
    if order.seller_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied.")
    if order.status not in ("ACCEPTED",):
        raise HTTPException(status_code=400, detail=f"Cannot ship order in status {order.status}.")
    order.status = "SHIPPED"
    db.commit()
    db.refresh(order)
    emit_event(db, user_id=current_user.user_id, role="seller",
               event_type="ORDER_SHIPPED", transaction_id=order.order_id)
    return order


# ── Seller: Deliver ────────────────────────────────────────────────────────────

@router.post("/{order_id}/deliver", response_model=OrderRead)
def deliver_order(
    order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "seller":
        raise HTTPException(status_code=403, detail="Only sellers can mark delivered.")
    order = _get_order_or_404(db, order_id)
    if order.seller_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied.")
    if order.status != "SHIPPED":
        raise HTTPException(status_code=400, detail=f"Cannot deliver order in status {order.status}.")
    order.status = "DELIVERED"
    db.commit()
    db.refresh(order)
    emit_event(db, user_id=current_user.user_id, role="seller",
               event_type="ORDER_DELIVERED", transaction_id=order.order_id)
    # Buyer: ORDER_COMPLETED
    emit_event(db, user_id=order.buyer_id, role="buyer",
               event_type="ORDER_COMPLETED", transaction_id=order.order_id)
    return order


# ── Buyer: Pay ─────────────────────────────────────────────────────────────────

@router.post("/{order_id}/pay", response_model=PaymentRead, status_code=201)
def pay_order(
    order_id: str,
    data: PaymentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "buyer":
        raise HTTPException(status_code=403, detail="Only buyers can pay.")
    order = _get_order_or_404(db, order_id)
    if order.buyer_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied.")
    if order.status not in ("PLACED", "ACCEPTED"):
        raise HTTPException(status_code=400, detail=f"Cannot pay for order in status {order.status}.")
    # Simulated payment: always SUCCESS in demo (CARD_SIMULATED / WALLET).
    # COD is marked SUCCESS immediately as well.
    payment = Payment(
        payment_id=f"PAY-{uuid.uuid4().hex[:8].upper()}",
        order_id=order_id,
        buyer_id=current_user.user_id,
        amount=order.total_amount,
        status="SUCCESS",
        method=data.method,
    )
    order.status = "COMPLETED"
    db.add(payment)
    db.commit()
    db.refresh(payment)
    emit_event(db, user_id=current_user.user_id, role="buyer",
               event_type="PAYMENT_SUCCESS", transaction_id=order.order_id,
               metadata={"method": data.method})
    emit_event(db, user_id=order.seller_id, role="seller",
               event_type="ORDER_FULFILLED", transaction_id=order.order_id)
    return payment


# ── Buyer: Return ──────────────────────────────────────────────────────────────

@router.post("/{order_id}/return", response_model=ReturnRead, status_code=201)
def request_return(
    order_id: str,
    data: ReturnCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "buyer":
        raise HTTPException(status_code=403, detail="Only buyers can request returns.")
    order = _get_order_or_404(db, order_id)
    if order.buyer_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied.")
    if order.status not in ("DELIVERED", "COMPLETED"):
        raise HTTPException(status_code=400, detail="Can only return delivered/completed orders.")
    existing = db.query(Return).filter(Return.order_id == order_id).first()
    if existing:
        raise HTTPException(status_code=409, detail="Return already requested for this order.")

    ret = Return(
        return_id=f"RET-{uuid.uuid4().hex[:8].upper()}",
        order_id=order_id,
        buyer_id=current_user.user_id,
        seller_id=order.seller_id,
        reason=data.reason,
        is_problematic=False,   # seller or admin can flag later
        status="REQUESTED",
    )
    order.status = "RETURN_REQUESTED"
    db.add(ret)
    db.commit()
    db.refresh(ret)
    emit_event(db, user_id=current_user.user_id, role="buyer",
               event_type="RETURN_REQUESTED", transaction_id=order.order_id)
    emit_event(db, user_id=order.seller_id, role="seller",
               event_type="RETURN_REQUEST_RECEIVED", transaction_id=order.order_id)
    return ret


# ── Buyer: Review ──────────────────────────────────────────────────────────────

@router.post("/{order_id}/review", response_model=ReviewRead, status_code=201)
def submit_review(
    order_id: str,
    data: ReviewCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "buyer":
        raise HTTPException(status_code=403, detail="Only buyers can submit reviews.")
    order = _get_order_or_404(db, order_id)
    if order.buyer_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied.")
    if order.status not in ("DELIVERED", "COMPLETED"):
        raise HTTPException(status_code=400, detail="Can only review delivered/completed orders.")
    existing = db.query(Review).filter(Review.order_id == order_id).first()
    if existing:
        raise HTTPException(status_code=409, detail="Review already submitted for this order.")

    review = Review(
        review_id=f"REV-{uuid.uuid4().hex[:8].upper()}",
        order_id=order_id,
        buyer_id=current_user.user_id,
        seller_id=order.seller_id,
        rating=data.rating,
        comment=data.comment,
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    emit_event(db, user_id=current_user.user_id, role="buyer",
               event_type="REVIEW_SUBMITTED", transaction_id=order.order_id,
               metadata={"rating": data.rating})
    emit_event(db, user_id=order.seller_id, role="seller",
               event_type="REVIEW_RECEIVED", transaction_id=order.order_id,
               metadata={"rating": data.rating})
    return review
