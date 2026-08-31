"""
TrustGrid Feature Engine.

Responsibilities:
  1. Pull all TrustEvent rows for a user from the database.
  2. Apply exponential time decay with a 90-day half-life so that
     recent actions have greater influence than old ones.
  3. Aggregate decayed events into a behavioural feature vector
     (rates, counts, weighted averages).
  4. Persist the feature vector into the behavior_features table.

Design notes:
  ─ Decay formula: w = exp(−λ · age_days),  λ = ln(2) / 90 ≈ 0.00770
  ─ A brand-new user with zero events gets a neutral feature vector
    (all rates at 1.0 / counts at 0) so the initial 700 score holds.
  ─ We never penalise infrequent buyers: purchase frequency is NOT
    a direct feature.  Only reliability rates are used.
  ─ The same function is called for both buyers and sellers;
    irrelevant fields simply stay at their default neutral values.
"""
import math
from datetime import datetime, timezone
from typing import List

from sqlalchemy.orm import Session

from app.models.trust import BehaviorFeatures, TrustEvent
from app.trustgrid.event_types import EventType


# ── Decay constant ────────────────────────────────────────────────────────────

_HALF_LIFE_DAYS: float = 90.0
_LAMBDA: float = math.log(2) / _HALF_LIFE_DAYS   # ≈ 0.007702


def decay_weight(event_time: datetime, now: datetime) -> float:
    """
    Return the exponential decay weight for an event.

    weight(age_days) = exp(−λ × age_days)

    Weights by age:
        0 days   → 1.000
        30 days  → 0.794
        90 days  → 0.500
        180 days → 0.250
        270 days → 0.125
    """
    if event_time.tzinfo is None:
        event_time = event_time.replace(tzinfo=timezone.utc)
    age_days = max(0.0, (now - event_time).total_seconds() / 86_400)
    return math.exp(-_LAMBDA * age_days)


# ── Main entry point ──────────────────────────────────────────────────────────

def update_features(db: Session, user_id: str) -> BehaviorFeatures:
    """
    Recalculate and persist the feature vector for one user.
    Called after every trust event for that user.
    Only the affected user is recalculated (never all users).
    """
    events: List[TrustEvent] = (
        db.query(TrustEvent)
        .filter(TrustEvent.user_id == user_id)
        .order_by(TrustEvent.created_at.asc())
        .all()
    )

    now = datetime.now(timezone.utc)
    features = _compute_features(events, now)

    # Upsert into behavior_features
    # expire_all() clears the session identity map so we always read fresh from DB
    db.expire_all()
    row = db.query(BehaviorFeatures).filter(BehaviorFeatures.user_id == user_id).first()
    if row is None:
        row = BehaviorFeatures(user_id=user_id)
        db.add(row)

    # Assign every computed field
    for attr, value in features.items():
        setattr(row, attr, value)

    db.commit()
    db.refresh(row)
    return row


# ── Feature computation ───────────────────────────────────────────────────────

def _compute_features(events: List[TrustEvent], now: datetime) -> dict:
    """
    Aggregate all events into a feature dict.
    All rates are decayed-weighted; counts are simple integers.
    """

    # ── Accumulators (decayed) ────────────────────────────────────────────────
    # Buyer
    w_orders_placed       = 0.0   # decayed sum of ORDER_PLACED
    w_orders_completed    = 0.0   # decayed sum of ORDER_COMPLETED
    w_orders_cancelled    = 0.0   # decayed sum of ORDER_CANCELLED (buyer side)
    w_payments_attempted  = 0.0   # ORDER_PLACED implies a payment attempt
    w_payments_success    = 0.0   # PAYMENT_SUCCESS
    w_payments_failed     = 0.0   # PAYMENT_FAILED
    w_returns_requested   = 0.0   # RETURN_REQUESTED
    referral_count        = 0     # integer count (not decayed — a referral is permanent)
    review_count          = 0     # integer count

    # Seller
    w_orders_to_fulfill   = 0.0   # ORDER_PLACED that came to seller (proxy: delivered + fulfilled + cancelled)
    w_fulfilled           = 0.0   # ORDER_FULFILLED (shipped)
    w_delivered           = 0.0   # ORDER_DELIVERED (completed)
    w_seller_cancelled    = 0.0   # SELLER_CANCELLED
    w_late_deliveries     = 0.0   # ORDER_LATE
    w_ratings_sum         = 0.0   # sum of decayed rating values
    w_ratings_count       = 0.0   # decayed count of ratings received
    w_return_requests     = 0.0   # RETURN_REQUEST_RECEIVED
    w_return_resolved     = 0.0   # RETURN_RESOLVED
    w_return_rejected     = 0.0   # RETURN_REJECTED
    products_listed       = 0     # integer count of PRODUCT_LISTED events

    # Total decayed event weight (proxy for evidence volume)
    total_decayed_weight  = 0.0

    for ev in events:
        w = decay_weight(ev.created_at, now)
        total_decayed_weight += w
        etype = ev.event_type

        # ── Buyer accumulators ────────────────────────────────────────────────
        if etype == EventType.ORDER_PLACED.value:
            w_orders_placed      += w
            w_payments_attempted += w          # every placement = payment attempt

        elif etype == EventType.ORDER_COMPLETED.value:
            w_orders_completed   += w

        elif etype == EventType.ORDER_CANCELLED.value:
            w_orders_cancelled   += w

        elif etype == EventType.PAYMENT_SUCCESS.value:
            w_payments_success   += w

        elif etype == EventType.PAYMENT_FAILED.value:
            w_payments_failed    += w
            w_payments_attempted += w          # failed payment also counts as attempt

        elif etype == EventType.RETURN_REQUESTED.value:
            w_returns_requested  += w

        elif etype == EventType.REFERRAL_COMPLETED.value:
            referral_count       += 1          # permanent credit

        elif etype == EventType.REVIEW_SUBMITTED.value:
            review_count         += 1

        # ── Seller accumulators ───────────────────────────────────────────────
        elif etype == EventType.ORDER_FULFILLED.value:
            w_fulfilled          += w
            w_orders_to_fulfill  += w          # proxy denominator

        elif etype == EventType.ORDER_DELIVERED.value:
            w_delivered          += w

        elif etype == EventType.SELLER_CANCELLED.value:
            w_seller_cancelled   += w
            w_orders_to_fulfill  += w          # also counts as an order that needed fulfilling

        elif etype == EventType.ORDER_LATE.value:
            w_late_deliveries    += w

        elif etype == EventType.REVIEW_RECEIVED.value:
            rating = (ev.metadata_ or {}).get("rating", 0)
            if rating:
                w_ratings_sum    += w * float(rating)
                w_ratings_count  += w

        elif etype == EventType.RETURN_REQUEST_RECEIVED.value:
            w_return_requests    += w

        elif etype == EventType.RETURN_RESOLVED.value:
            w_return_resolved    += w

        elif etype == EventType.RETURN_REJECTED.value:
            w_return_rejected    += w

        elif etype == EventType.PRODUCT_LISTED.value:
            products_listed      += 1

    # ── Compute rates (safe division) ─────────────────────────────────────────

    # --- Buyer ---
    # Order completion rate: completed / placed  (only considers placed orders)
    order_completion_rate = _safe_rate(w_orders_completed, w_orders_placed)

    # Return rate: returns / completed orders
    return_rate = _safe_rate(w_returns_requested, w_orders_completed)

    # Payment success rate: successes / attempts
    payment_success_rate = _safe_rate(w_payments_success, w_payments_attempted)

    # Cancellation rate: cancellations / placed
    cancellation_rate = _safe_rate(w_orders_cancelled, w_orders_placed)

    # --- Seller ---
    # Fulfillment rate: fulfilled / (fulfilled + seller_cancelled)
    fulfillment_denominator = w_fulfilled + w_seller_cancelled
    fulfillment_rate = _safe_rate(w_fulfilled, fulfillment_denominator)

    # Late delivery rate: late / delivered
    late_delivery_rate = _safe_rate(w_late_deliveries, w_delivered)

    # Average rating received (decayed weighted average)
    avg_rating_received = (w_ratings_sum / w_ratings_count) if w_ratings_count > 0 else 0.0

    # Return response rate: (resolved + rejected) / requests_received
    returns_responded = w_return_resolved + w_return_rejected
    return_response_rate = _safe_rate(returns_responded, w_return_requests)

    # Counts (integer)
    total_orders       = max(0, round(w_orders_placed))
    completed_orders   = max(0, round(w_orders_completed))
    total_returns      = max(0, round(w_returns_requested))
    payment_attempts   = max(0, round(w_payments_attempted))
    successful_payments = max(0, round(w_payments_success))
    total_cancellations = max(0, round(w_orders_cancelled))
    fulfilled_orders   = max(0, round(w_fulfilled))
    seller_cancellations = max(0, round(w_seller_cancelled))
    on_time_deliveries = max(0, round(w_delivered - w_late_deliveries))
    late_deliveries    = max(0, round(w_late_deliveries))
    return_requests_received = max(0, round(w_return_requests))
    returns_responded_count  = max(0, round(returns_responded))

    return {
        # Buyer
        "total_orders":            total_orders,
        "completed_orders":        completed_orders,
        "order_completion_rate":   round(order_completion_rate, 4),
        "total_returns":           total_returns,
        "return_rate":             round(return_rate, 4),
        "payment_attempts":        payment_attempts,
        "successful_payments":     successful_payments,
        "payment_success_rate":    round(payment_success_rate, 4),
        "total_cancellations":     total_cancellations,
        "cancellation_rate":       round(cancellation_rate, 4),
        "referral_count":          referral_count,
        "review_count":            review_count,
        # Seller
        "fulfilled_orders":        fulfilled_orders,
        "seller_cancellations":    seller_cancellations,
        "fulfillment_rate":        round(fulfillment_rate, 4),
        "on_time_deliveries":      on_time_deliveries,
        "late_deliveries":         late_deliveries,
        "late_delivery_rate":      round(late_delivery_rate, 4),
        "avg_rating_received":     round(avg_rating_received, 4),
        "return_requests_received": return_requests_received,
        "returns_responded":       returns_responded_count,
        "return_response_rate":    round(return_response_rate, 4),
        "products_listed":         products_listed,
        # Shared
        "decayed_event_weight":    round(total_decayed_weight, 4),
    }


# ── Utilities ─────────────────────────────────────────────────────────────────

def _safe_rate(numerator: float, denominator: float, default: float = 1.0) -> float:
    """
    Safe division for rates.
    Returns `default` when denominator is zero (no evidence → assume neutral).
    Neutral default is 1.0 (perfect rate) so new users are not penalised.
    """
    if denominator <= 0:
        return default
    return min(1.0, max(0.0, numerator / denominator))


def get_feature_vector(db: Session, user_id: str) -> dict:
    """
    Return the current feature vector for a user as a plain dict.
    If no row exists, returns neutral defaults.

    Uses a raw SQL query to guarantee we read the latest committed values,
    bypassing SQLAlchemy's identity-map cache.
    """
    from sqlalchemy import text
    result = db.execute(
        text("""
            SELECT total_orders, completed_orders, order_completion_rate,
                   total_returns, return_rate, payment_attempts,
                   successful_payments, payment_success_rate,
                   total_cancellations, cancellation_rate,
                   referral_count, review_count,
                   fulfilled_orders, seller_cancellations, fulfillment_rate,
                   on_time_deliveries, late_deliveries, late_delivery_rate,
                   avg_rating_received, return_requests_received,
                   returns_responded, return_response_rate,
                   products_listed, decayed_event_weight
            FROM behavior_features
            WHERE user_id = :uid
        """),
        {"uid": user_id},
    ).fetchone()

    if result is None:
        return _neutral_features()

    keys = [
        "total_orders", "completed_orders", "order_completion_rate",
        "total_returns", "return_rate", "payment_attempts",
        "successful_payments", "payment_success_rate",
        "total_cancellations", "cancellation_rate",
        "referral_count", "review_count",
        "fulfilled_orders", "seller_cancellations", "fulfillment_rate",
        "on_time_deliveries", "late_deliveries", "late_delivery_rate",
        "avg_rating_received", "return_requests_received",
        "returns_responded", "return_response_rate",
        "products_listed", "decayed_event_weight",
    ]
    return dict(zip(keys, result))


def _neutral_features() -> dict:
    """
    Neutral feature vector for brand-new users with no events.
    All rates are 1.0 (perfect) — no evidence yet, so we don't penalise.
    All counts are 0.
    """
    return {
        "total_orders": 0, "completed_orders": 0, "order_completion_rate": 1.0,
        "total_returns": 0, "return_rate": 0.0,
        "payment_attempts": 0, "successful_payments": 0, "payment_success_rate": 1.0,
        "total_cancellations": 0, "cancellation_rate": 0.0,
        "referral_count": 0, "review_count": 0,
        "fulfilled_orders": 0, "seller_cancellations": 0, "fulfillment_rate": 1.0,
        "on_time_deliveries": 0, "late_deliveries": 0, "late_delivery_rate": 0.0,
        "avg_rating_received": 0.0,
        "return_requests_received": 0, "returns_responded": 0, "return_response_rate": 1.0,
        "products_listed": 0, "decayed_event_weight": 0.0,
    }
