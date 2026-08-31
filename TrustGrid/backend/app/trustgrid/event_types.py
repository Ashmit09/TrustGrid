"""
TrustGrid Event Types.

All marketplace events that can influence a user's Trust Score are defined here.
Centralising them prevents magic strings scattered across the codebase.
"""
from enum import Enum


class EventType(str, Enum):
    # ── Buyer events ──────────────────────────────────────────────────────────
    ORDER_PLACED           = "ORDER_PLACED"
    ORDER_COMPLETED        = "ORDER_COMPLETED"       # buyer confirmed receipt
    ORDER_CANCELLED        = "ORDER_CANCELLED"       # buyer cancelled
    PAYMENT_SUCCESS        = "PAYMENT_SUCCESS"
    PAYMENT_FAILED         = "PAYMENT_FAILED"
    RETURN_REQUESTED       = "RETURN_REQUESTED"
    RETURN_COMPLETED       = "RETURN_COMPLETED"      # return resolved by seller
    REVIEW_SUBMITTED       = "REVIEW_SUBMITTED"
    REFERRAL_COMPLETED     = "REFERRAL_COMPLETED"

    # ── Seller events ─────────────────────────────────────────────────────────
    ORDER_FULFILLED        = "ORDER_FULFILLED"       # seller shipped
    ORDER_DELIVERED        = "ORDER_DELIVERED"       # buyer confirmed receipt (seller side)
    ORDER_LATE             = "ORDER_LATE"            # shipped but buyer waited too long
    SELLER_CANCELLED       = "SELLER_CANCELLED"      # seller cancelled buyer's order
    RETURN_REQUEST_RECEIVED = "RETURN_REQUEST_RECEIVED"
    RETURN_RESOLVED        = "RETURN_RESOLVED"       # seller resolved a return
    RETURN_REJECTED        = "RETURN_REJECTED"       # seller rejected a return request
    REVIEW_RECEIVED        = "REVIEW_RECEIVED"       # seller received a review
    PRODUCT_LISTED         = "PRODUCT_LISTED"

    # ── Shared ────────────────────────────────────────────────────────────────
    REFERRAL_MADE          = "REFERRAL_MADE"         # referrer side


# Events that contribute meaningful behavioral evidence for confidence scoring
MEANINGFUL_EVENTS = {
    EventType.ORDER_COMPLETED,
    EventType.PAYMENT_SUCCESS,
    EventType.REVIEW_SUBMITTED,
    EventType.REFERRAL_COMPLETED,
    EventType.ORDER_FULFILLED,
    EventType.ORDER_DELIVERED,
    EventType.RETURN_RESOLVED,
    EventType.REVIEW_RECEIVED,
}

# Events that negatively signal unreliable behaviour
NEGATIVE_EVENTS = {
    EventType.ORDER_CANCELLED,
    EventType.PAYMENT_FAILED,
    EventType.SELLER_CANCELLED,
    EventType.ORDER_LATE,
    EventType.RETURN_REJECTED,
}
