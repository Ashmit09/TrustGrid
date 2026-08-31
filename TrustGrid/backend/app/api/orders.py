"""
Order routes:
  POST /orders                        — buyer places order
  GET  /orders                        — list orders (buyer or seller)
  GET  /orders/{order_id}             — order detail
  POST /orders/{order_id}/cancel      — buyer or seller cancels
  POST /orders/{order_id}/ship        — seller ships
  POST /orders/{order_id}/complete    — buyer confirms receipt
  POST /orders/{order_id}/return      — buyer requests return
  POST /orders/{order_id}/review      — buyer submits review
  GET  /orders/returns                — seller views their return requests
  POST /orders/returns/{id}/resolve   — seller resolves a return
"""
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.order import (
    OrderCreate, OrderOut, ReturnCreate, ReturnOut, ReviewCreate, ReviewOut
)
from app.services.order_service import (
    place_order, cancel_order, ship_order, complete_order,
    request_return, submit_review, resolve_return,
    get_orders_for_user, get_returns_for_seller,
)
from app.core.dependencies import get_current_user_payload, require_role

router = APIRouter()


@router.post("", response_model=OrderOut, status_code=201, summary="Place an order (buyer)")
def place(
    data:    OrderCreate,
    payload: dict    = Depends(require_role("buyer")),
    db:      Session = Depends(get_db),
):
    return place_order(db, buyer_id=payload["sub"], data=data)


@router.get("", response_model=List[OrderOut], summary="List orders for authenticated user")
def list_orders(
    payload: dict    = Depends(get_current_user_payload),
    db:      Session = Depends(get_db),
):
    return get_orders_for_user(db, user_id=payload["sub"], role=payload["role"])


@router.get("/returns", response_model=List[ReturnOut], summary="Seller's return requests")
def list_returns(
    payload: dict    = Depends(require_role("seller")),
    db:      Session = Depends(get_db),
):
    return get_returns_for_seller(db, seller_id=payload["sub"])


@router.get("/{order_id}", response_model=OrderOut, summary="Get order detail")
def order_detail(
    order_id: str,
    payload:  dict    = Depends(get_current_user_payload),
    db:       Session = Depends(get_db),
):
    from app.services.order_service import _get_order_or_404
    from fastapi import HTTPException
    order = _get_order_or_404(db, order_id)
    # Only buyer, seller, or admin can view
    if payload["sub"] not in (order.buyer_id, order.seller_id) and payload["role"] != "admin":
        raise HTTPException(status_code=403, detail="Access denied.")
    return order


@router.post("/{order_id}/cancel", response_model=OrderOut, summary="Cancel order")
def cancel(
    order_id: str,
    payload:  dict    = Depends(get_current_user_payload),
    db:       Session = Depends(get_db),
):
    return cancel_order(db, order_id=order_id, user_id=payload["sub"], role=payload["role"])


@router.post("/{order_id}/ship", response_model=OrderOut, summary="Mark order shipped (seller)")
def ship(
    order_id: str,
    payload:  dict    = Depends(require_role("seller")),
    db:       Session = Depends(get_db),
):
    return ship_order(db, order_id=order_id, seller_id=payload["sub"])


@router.post("/{order_id}/complete", response_model=OrderOut, summary="Confirm receipt (buyer)")
def complete(
    order_id: str,
    payload:  dict    = Depends(require_role("buyer")),
    db:       Session = Depends(get_db),
):
    return complete_order(db, order_id=order_id, buyer_id=payload["sub"])


@router.post("/{order_id}/return", response_model=ReturnOut, summary="Request return (buyer)")
def return_request(
    order_id: str,
    data:     ReturnCreate,
    payload:  dict    = Depends(require_role("buyer")),
    db:       Session = Depends(get_db),
):
    return request_return(db, order_id=order_id, buyer_id=payload["sub"], data=data)


@router.post("/{order_id}/review", response_model=ReviewOut, summary="Submit review (buyer)")
def review(
    order_id: str,
    data:     ReviewCreate,
    payload:  dict    = Depends(require_role("buyer")),
    db:       Session = Depends(get_db),
):
    return submit_review(db, order_id=order_id, buyer_id=payload["sub"], data=data)


@router.post(
    "/returns/{return_id}/resolve",
    response_model=ReturnOut,
    summary="Resolve a return request (seller)",
)
def resolve(
    return_id:  int,
    resolution: str,
    payload:    dict    = Depends(require_role("seller")),
    db:         Session = Depends(get_db),
):
    return resolve_return(db, return_id=return_id, seller_id=payload["sub"], resolution=resolution)
