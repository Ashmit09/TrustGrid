"""
Order service — place, cancel, ship, complete, return, review.

Simulated payment: a random outcome (95% success rate) is used.
Every marketplace action fires the appropriate TrustGrid event, then
triggers feature recalculation for all affected users.

Feature recalculation is called AFTER the event-recording transaction
commits, so that the Feature Engine reads up-to-date event rows.
"""
import random
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import List

from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.marketplace import Order, Payment, Return, Review, Referral
from app.models.marketplace import OrderStatus, PaymentStatus, ReturnStatus
from app.models.product import Product
from app.schemas.order import OrderCreate, ReturnCreate, ReviewCreate
from app.trustgrid.event_service import record_event, record_events_batch, update_features_for_users
from app.trustgrid.event_types import EventType
from app.services import trust_service as _trust_svc


# ── Helpers ───────────────────────────────────────────────────────────────────

def _generate_order_id() -> str:
    return f"ORD-{uuid.uuid4().hex[:10].upper()}"


def _simulate_payment(amount: Decimal) -> PaymentStatus:
    """95 % success rate — simulates real-world payment reliability."""
    return PaymentStatus.success if random.random() < 0.95 else PaymentStatus.failed


# ── Place order ───────────────────────────────────────────────────────────────

def place_order(db: Session, buyer_id: str, data: OrderCreate) -> Order:
    """
    1. Validate product exists and has stock.
    2. Create Order (pending).
    3. Simulate payment → update order status.
    4. Decrement stock on success.
    5. Fire TrustGrid events, then recalculate buyer features.
    """
    product: Product = db.query(Product).filter(
        Product.id == data.product_id,
        Product.is_active == True,
    ).first()

    if not product:
        raise HTTPException(status_code=404, detail="Product not found or inactive.")
    if product.stock < data.quantity:
        raise HTTPException(status_code=400, detail="Insufficient stock.")
    if product.seller_id == buyer_id:
        raise HTTPException(status_code=400, detail="Cannot purchase your own product.")

    unit_price   = product.price
    total_amount = unit_price * data.quantity
    order_id     = _generate_order_id()

    order = Order(
        order_id=order_id,
        buyer_id=buyer_id,
        seller_id=product.seller_id,
        product_id=product.id,
        quantity=data.quantity,
        unit_price=unit_price,
        total_amount=total_amount,
        status=OrderStatus.pending,
    )
    db.add(order)
    db.flush()

    # Simulate payment
    pay_status = _simulate_payment(total_amount)
    payment = Payment(
        order_id=order_id,
        buyer_id=buyer_id,
        amount=total_amount,
        status=pay_status,
    )
    db.add(payment)

    if pay_status == PaymentStatus.success:
        order.status = OrderStatus.paid
        product.stock -= data.quantity
    else:
        order.status = OrderStatus.cancelled   # failed payment = auto-cancel

    db.commit()
    db.refresh(order)

    # ── Fire TrustGrid events (each call is its own commit) ───────────────────
    record_event(db, buyer_id, EventType.ORDER_PLACED,
                 reference_id=order_id,
                 impact_summary="Placed an order")

    if pay_status == PaymentStatus.success:
        record_event(db, buyer_id, EventType.PAYMENT_SUCCESS,
                     reference_id=order_id,
                     metadata={"amount": float(total_amount)},
                     impact_summary="Successful payment")
    else:
        record_event(db, buyer_id, EventType.PAYMENT_FAILED,
                     reference_id=order_id,
                     metadata={"amount": float(total_amount)},
                     impact_summary="Payment failed")

    # ── Recalculate features + trust score AFTER all events are committed ─────
    update_features_for_users(db, [buyer_id])
    _trust_svc.refresh_trust(db, buyer_id,
                              event_type=EventType.ORDER_PLACED.value,
                              reason="Order placed and payment processed.")
    return order


# ── Cancel order ──────────────────────────────────────────────────────────────

def cancel_order(db: Session, order_id: str, user_id: str, role: str) -> Order:
    order = _get_order_or_404(db, order_id)

    if role == "buyer":
        if order.buyer_id != user_id:
            raise HTTPException(status_code=403, detail="Access denied.")
        if order.status not in (OrderStatus.pending, OrderStatus.paid):
            raise HTTPException(status_code=400, detail=f"Cannot cancel order in '{order.status}' state.")
        order.status = OrderStatus.cancelled

    elif role == "seller":
        if order.seller_id != user_id:
            raise HTTPException(status_code=403, detail="Access denied.")
        if order.status not in (OrderStatus.paid, OrderStatus.shipped):
            raise HTTPException(status_code=400, detail=f"Cannot cancel order in '{order.status}' state.")
        order.status = OrderStatus.cancelled

    db.commit()
    db.refresh(order)

    if role == "buyer":
        record_event(db, order.buyer_id, EventType.ORDER_CANCELLED,
                     reference_id=order.order_id,
                     impact_summary="Cancelled an order")
        update_features_for_users(db, [order.buyer_id])
        _trust_svc.refresh_trust(db, order.buyer_id,
                                  event_type=EventType.ORDER_CANCELLED.value,
                                  reason="Order cancelled by buyer.")
    else:
        record_event(db, order.seller_id, EventType.SELLER_CANCELLED,
                     reference_id=order.order_id,
                     impact_summary="Seller cancelled an order")
        update_features_for_users(db, [order.seller_id])
        _trust_svc.refresh_trust(db, order.seller_id,
                                  event_type=EventType.SELLER_CANCELLED.value,
                                  reason="Order cancelled by seller.")

    return order


# ── Ship order (seller) ───────────────────────────────────────────────────────

def ship_order(db: Session, order_id: str, seller_id: str) -> Order:
    order = _get_order_or_404(db, order_id)
    if order.seller_id != seller_id:
        raise HTTPException(status_code=403, detail="Access denied.")
    if order.status != OrderStatus.paid:
        raise HTTPException(status_code=400, detail="Order must be paid before shipping.")
    order.status = OrderStatus.shipped
    db.commit()
    db.refresh(order)

    record_event(db, seller_id, EventType.ORDER_FULFILLED,
                 reference_id=order.order_id,
                 impact_summary="Order shipped to buyer")
    update_features_for_users(db, [seller_id])
    _trust_svc.refresh_trust(db, seller_id,
                              event_type=EventType.ORDER_FULFILLED.value,
                              reason="Order shipped to buyer.")
    return order


# ── Complete order (buyer confirms receipt) ───────────────────────────────────

def complete_order(db: Session, order_id: str, buyer_id: str) -> Order:
    order = _get_order_or_404(db, order_id)
    if order.buyer_id != buyer_id:
        raise HTTPException(status_code=403, detail="Access denied.")
    if order.status != OrderStatus.shipped:
        raise HTTPException(status_code=400, detail="Order must be shipped before completion.")
    order.status = OrderStatus.completed
    order.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(order)

    seller_id = order.seller_id
    record_events_batch(db, [
        {
            "user_id":        buyer_id,
            "event_type":     EventType.ORDER_COMPLETED,
            "reference_id":   order.order_id,
            "impact_summary": "Successfully completed an order",
        },
        {
            "user_id":        seller_id,
            "event_type":     EventType.ORDER_DELIVERED,
            "reference_id":   order.order_id,
            "impact_summary": "Order delivered to buyer",
        },
    ])
    update_features_for_users(db, [buyer_id, seller_id])
    _trust_svc.refresh_trust(db, buyer_id,
                              event_type=EventType.ORDER_COMPLETED.value,
                              reason="Order successfully completed.")
    _trust_svc.refresh_trust(db, seller_id,
                              event_type=EventType.ORDER_DELIVERED.value,
                              reason="Order delivered to buyer.")
    return order


# ── Return request (buyer) ────────────────────────────────────────────────────

def request_return(db: Session, order_id: str, buyer_id: str, data: ReturnCreate) -> Return:
    order = _get_order_or_404(db, order_id)
    if order.buyer_id != buyer_id:
        raise HTTPException(status_code=403, detail="Access denied.")

    # Check for duplicate before status guard so we always return 409 on re-submission
    existing = db.query(Return).filter(Return.order_id == order_id).first()
    if existing:
        raise HTTPException(status_code=409, detail="Return already requested for this order.")

    # Allow return on completed, shipped, or returned (status is set to 'returned' after first request)
    if order.status not in (OrderStatus.completed, OrderStatus.shipped, OrderStatus.returned):
        raise HTTPException(status_code=400, detail="Order must be completed or shipped to request a return.")

    ret = Return(
        order_id=order_id,
        buyer_id=buyer_id,
        seller_id=order.seller_id,
        reason=data.reason,
        status=ReturnStatus.pending,
    )
    db.add(ret)
    order.status = OrderStatus.returned
    db.commit()
    db.refresh(ret)

    seller_id = order.seller_id
    record_events_batch(db, [
        {
            "user_id":        buyer_id,
            "event_type":     EventType.RETURN_REQUESTED,
            "reference_id":   order_id,
            "impact_summary": "Requested a return",
        },
        {
            "user_id":        seller_id,
            "event_type":     EventType.RETURN_REQUEST_RECEIVED,
            "reference_id":   order_id,
            "impact_summary": "Received a return request",
        },
    ])
    update_features_for_users(db, [buyer_id, seller_id])
    _trust_svc.refresh_trust(db, buyer_id,
                              event_type=EventType.RETURN_REQUESTED.value,
                              reason="Return requested.")
    _trust_svc.refresh_trust(db, seller_id,
                              event_type=EventType.RETURN_REQUEST_RECEIVED.value,
                              reason="Return request received from buyer.")
    return ret


# ── Submit review (buyer) ─────────────────────────────────────────────────────

def submit_review(db: Session, order_id: str, buyer_id: str, data: ReviewCreate) -> Review:
    order = _get_order_or_404(db, order_id)
    if order.buyer_id != buyer_id:
        raise HTTPException(status_code=403, detail="Access denied.")
    if order.status != OrderStatus.completed:
        raise HTTPException(status_code=400, detail="Order must be completed before leaving a review.")

    existing = db.query(Review).filter(Review.order_id == order_id).first()
    if existing:
        raise HTTPException(status_code=409, detail="Review already submitted for this order.")

    review = Review(
        order_id=order_id,
        reviewer_id=buyer_id,
        seller_id=order.seller_id,
        rating=data.rating,
        comment=data.comment,
    )
    db.add(review)
    db.commit()
    db.refresh(review)

    seller_id = order.seller_id
    record_events_batch(db, [
        {
            "user_id":        buyer_id,
            "event_type":     EventType.REVIEW_SUBMITTED,
            "reference_id":   order_id,
            "metadata":       {"rating": data.rating},
            "impact_summary": f"Submitted a {data.rating}-star review",
        },
        {
            "user_id":        seller_id,
            "event_type":     EventType.REVIEW_RECEIVED,
            "reference_id":   order_id,
            "metadata":       {"rating": data.rating},
            "impact_summary": f"Received a {data.rating}-star review",
        },
    ])
    update_features_for_users(db, [buyer_id, seller_id])
    _trust_svc.refresh_trust(db, buyer_id,
                              event_type=EventType.REVIEW_SUBMITTED.value,
                              reason=f"Submitted a {data.rating}-star review.")
    _trust_svc.refresh_trust(db, seller_id,
                              event_type=EventType.REVIEW_RECEIVED.value,
                              reason=f"Received a {data.rating}-star review.")
    return review


# ── Resolve return (seller) ───────────────────────────────────────────────────

def resolve_return(db: Session, return_id: int, seller_id: str, resolution: str) -> Return:
    ret = db.query(Return).filter(Return.id == return_id).first()
    if not ret:
        raise HTTPException(status_code=404, detail="Return not found.")
    if ret.seller_id != seller_id:
        raise HTTPException(status_code=403, detail="Access denied.")
    if ret.status != ReturnStatus.pending:
        raise HTTPException(status_code=400, detail="Return already resolved.")

    if resolution not in ("resolved", "rejected"):
        raise HTTPException(status_code=400, detail="Resolution must be 'resolved' or 'rejected'.")

    ret.status = ReturnStatus(resolution)
    ret.resolved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(ret)

    buyer_id = ret.buyer_id
    if resolution == "resolved":
        record_events_batch(db, [
            {
                "user_id":        seller_id,
                "event_type":     EventType.RETURN_RESOLVED,
                "reference_id":   str(return_id),
                "impact_summary": "Resolved a return request",
            },
            {
                "user_id":        buyer_id,
                "event_type":     EventType.RETURN_COMPLETED,
                "reference_id":   str(return_id),
                "impact_summary": "Return resolved by seller",
            },
        ])
        update_features_for_users(db, [seller_id, buyer_id])
        _trust_svc.refresh_trust(db, seller_id,
                                  event_type=EventType.RETURN_RESOLVED.value,
                                  reason="Return resolved for buyer.")
        _trust_svc.refresh_trust(db, buyer_id,
                                  event_type=EventType.RETURN_COMPLETED.value,
                                  reason="Return completed.")
    else:
        record_event(db, seller_id, EventType.RETURN_REJECTED,
                     reference_id=str(return_id),
                     impact_summary="Rejected a return request")
        update_features_for_users(db, [seller_id])
        _trust_svc.refresh_trust(db, seller_id,
                                  event_type=EventType.RETURN_REJECTED.value,
                                  reason="Return request rejected.")

    return ret


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_order_or_404(db: Session, order_id: str) -> Order:
    order = db.query(Order).filter(Order.order_id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")
    return order


def get_orders_for_user(db: Session, user_id: str, role: str) -> List[Order]:
    if role == "buyer":
        return db.query(Order).filter(Order.buyer_id == user_id).order_by(Order.created_at.desc()).all()
    else:
        return db.query(Order).filter(Order.seller_id == user_id).order_by(Order.created_at.desc()).all()


def get_returns_for_seller(db: Session, seller_id: str) -> List[Return]:
    return db.query(Return).filter(Return.seller_id == seller_id).order_by(Return.created_at.desc()).all()
