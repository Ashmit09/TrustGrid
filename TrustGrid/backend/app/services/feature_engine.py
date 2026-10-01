"""
TrustGrid — Feature Engine

Converts a user's raw trust events (with timestamps) into a flat dict of
time-decayed behavioral features.  These features are consumed by:
  1. The dimension scorer (rule-based dimensions D1–D5)
  2. The XGBoost model (ML prediction)

The engine is PURE — it takes events as a list of dicts and a reference
timestamp and returns a feature dict. No database access here.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.services.time_decay import event_age_days, decayed_rate, decayed_average


EventList = List[Dict[str, Any]]


# ── Buyer Feature Builder ─────────────────────────────────────────────────────

def build_buyer_features(
    events: EventList,
    *,
    reference_ts: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Build decayed behavioral features for a buyer.

    Parameters
    ----------
    events        : list of trust event dicts (must contain 'event_type', 'created_at',
                    and optionally 'metadata_' for rich fields like is_problematic)
    reference_ts  : the timestamp at which the score is being calculated (default: now)

    Returns
    -------
    Dict of feature name → numeric value.
    """
    if reference_ts is None:
        reference_ts = datetime.now(timezone.utc)

    # Separate events by type
    order_completed   = _filter(events, "ORDER_COMPLETED")
    order_cancelled   = _filter(events, "ORDER_CANCELLED")
    payment_success   = _filter(events, "PAYMENT_SUCCESS")
    payment_failed    = _filter(events, "PAYMENT_FAILED")
    return_requested  = _filter(events, "RETURN_REQUESTED")
    return_completed  = _filter(events, "RETURN_COMPLETED")
    review_submitted  = _filter(events, "REVIEW_SUBMITTED")
    referral_completed = _filter(events, "REFERRAL_COMPLETED")

    # All order-eligible events for order reliability
    order_events = order_completed + order_cancelled
    order_pairs = [(_age(e, reference_ts), 1) for e in order_completed] + \
                  [(_age(e, reference_ts), 0) for e in order_cancelled]

    # Payment reliability
    payment_events = payment_success + payment_failed
    payment_pairs  = [(_age(e, reference_ts), 1) for e in payment_success] + \
                     [(_age(e, reference_ts), 0) for e in payment_failed]

    # Return behaviour — split problematic vs non-problematic
    # A return is problematic if metadata_.get('is_problematic') == True
    # Legitimate returns are NOT counted as negative events (spec §5)
    problematic_returns = [
        e for e in return_requested
        if _meta(e).get("is_problematic", False)
    ]
    non_problematic_returns = [
        e for e in return_requested
        if not _meta(e).get("is_problematic", False)
    ]
    # For return behaviour dimension: problematic = 0 (negative), non-problematic = not counted
    # Eligible = all returns; positive = non-problematic returns
    return_pairs = [(_age(e, reference_ts), 0) for e in problematic_returns] + \
                   [(_age(e, reference_ts), 1) for e in non_problematic_returns]

    # Cancellation behaviour
    # All orders (completed + cancelled) are eligible; cancelled = negative
    cancellation_pairs = [(_age(e, reference_ts), 0) for e in order_cancelled] + \
                         [(_age(e, reference_ts), 1) for e in order_completed]

    # Platform engagement quality
    # Normalize: each useful review contributes 1 engagement unit, each referral contributes 2
    # Cap at meaningful saturation rather than rewarding raw volume
    engagement_events = review_submitted + referral_completed
    raw_score = len(review_submitted) + 2 * len(referral_completed)
    # Saturate at 20 engagement points = full score (normalized to 0–1)
    engagement_quality = min(1.0, raw_score / 20.0)

    # Count-based features for ML and confidence
    total_events = len(events)
    meaningful_event_count = len(order_events) + len(payment_events) + len(return_requested) + \
                             len(review_submitted) + len(referral_completed)

    # Recent vs historical activity (last 30 days vs older)
    recent_orders  = sum(1 for e in order_events     if _age(e, reference_ts) <= 30)
    recent_cancels = sum(1 for e in order_cancelled  if _age(e, reference_ts) <= 30)

    # Account age (days from first event to reference)
    account_age_days = _account_age(events, reference_ts)

    return {
        # Decayed rates (for dimensions)
        "decayed_completion_rate":       decayed_rate(order_pairs,      default_if_empty=0.5),
        "decayed_problematic_return_rate": 1.0 - decayed_rate(return_pairs, default_if_empty=0.5)
                                           if return_pairs else 0.0,
        "decayed_payment_success_rate":  decayed_rate(payment_pairs,   default_if_empty=0.5),
        "decayed_cancellation_rate":     1.0 - decayed_rate(cancellation_pairs, default_if_empty=0.5)
                                          if cancellation_pairs else 0.0,
        "engagement_quality":            engagement_quality,

        # Raw counts (for confidence and ML)
        "total_orders":          len(order_events),
        "completed_orders":      len(order_completed),
        "cancelled_orders":      len(order_cancelled),
        "total_payments":        len(payment_events),
        "failed_payments":       len(payment_failed),
        "total_returns":         len(return_requested),
        "problematic_returns":   len(problematic_returns),
        "total_reviews":         len(review_submitted),
        "total_referrals":       len(referral_completed),
        "meaningful_event_count": meaningful_event_count,
        "total_event_count":     total_events,
        "recent_orders_30d":     recent_orders,
        "recent_cancels_30d":    recent_cancels,
        "account_age_days":      account_age_days,

        # Role tag (for ML feature alignment)
        "role": "buyer",
    }


# ── Seller Feature Builder ─────────────────────────────────────────────────────

def build_seller_features(
    events: EventList,
    *,
    reference_ts: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Build decayed behavioral features for a seller.
    """
    if reference_ts is None:
        reference_ts = datetime.now(timezone.utc)

    order_accepted    = _filter(events, "ORDER_ACCEPTED")
    order_fulfilled   = _filter(events, "ORDER_FULFILLED")
    order_shipped     = _filter(events, "ORDER_SHIPPED")
    order_delivered   = _filter(events, "ORDER_DELIVERED")
    order_late        = _filter(events, "ORDER_LATE")
    seller_cancelled  = _filter(events, "SELLER_CANCELLED")
    return_received   = _filter(events, "RETURN_REQUEST_RECEIVED")
    return_resolved   = _filter(events, "RETURN_RESOLVED")
    review_received   = _filter(events, "REVIEW_RECEIVED")
    product_listed    = _filter(events, "PRODUCT_LISTED")

    # Order Fulfillment: fulfilled / (fulfilled + seller_cancelled)
    fulfillment_eligible = order_fulfilled + seller_cancelled
    fulfillment_pairs = [(_age(e, reference_ts), 1) for e in order_fulfilled] + \
                        [(_age(e, reference_ts), 0) for e in seller_cancelled]

    # Delivery Performance: on-time vs late
    delivery_eligible = order_delivered + order_late
    delivery_pairs = [(_age(e, reference_ts), 1) for e in order_delivered] + \
                     [(_age(e, reference_ts), 0) for e in order_late]

    # Customer Satisfaction: decayed average rating (1–5 scale)
    rating_values = [
        (_age(e, reference_ts), float(_meta(e).get("rating", 3.0)))
        for e in review_received
        if "rating" in _meta(e)
    ]
    avg_rating = decayed_average(rating_values, default_if_empty=3.0)   # 1–5

    # Return & Dispute Handling: resolved / (received)
    dispute_pairs = [(_age(e, reference_ts), 1) for e in return_resolved] + \
                    [(_age(e, reference_ts), 0) for e in
                     [r for r in return_received
                      if not any(_meta(rr).get("order_id") == _meta(r).get("order_id")
                                 for rr in return_resolved)]]
    # Simpler: rate = resolved / total received
    if return_received:
        resolution_pairs = [
            (_age(e, reference_ts), 1) for e in return_resolved
        ] + [
            (_age(e, reference_ts), 0) for e in return_received
            if e not in return_resolved
        ]
        # We approximate: all received minus resolved = unresolved
        total_received_weight = sum(
            1 for e in return_received
        )
        resolution_pairs = [(_age(e, reference_ts), 1) for e in return_resolved[:total_received_weight]] + \
                           [(_age(e, reference_ts), 0) for e in return_received[len(return_resolved):]]
    else:
        resolution_pairs = []

    # Platform Reliability: normalize product listings up to saturation
    platform_reliability = min(1.0, len(product_listed) / 10.0)

    meaningful_event_count = (
        len(fulfillment_eligible) + len(delivery_eligible) +
        len(review_received) + len(return_received)
    )
    account_age_days = _account_age(events, reference_ts)
    recent_deliveries = sum(1 for e in order_delivered if _age(e, reference_ts) <= 30)
    recent_late       = sum(1 for e in order_late       if _age(e, reference_ts) <= 30)

    return {
        # Decayed rates (for dimensions)
        "decayed_fulfillment_rate":      decayed_rate(fulfillment_pairs, default_if_empty=0.5),
        "decayed_late_delivery_rate":    1.0 - decayed_rate(delivery_pairs, default_if_empty=0.5)
                                          if delivery_pairs else 0.0,
        "avg_rating_decayed":            avg_rating,
        "decayed_resolution_rate":       decayed_rate(resolution_pairs, default_if_empty=0.5),
        "platform_reliability":          platform_reliability,

        # Raw counts
        "total_fulfilled":       len(order_fulfilled),
        "total_cancelled_seller": len(seller_cancelled),
        "total_delivered":       len(order_delivered),
        "total_late":            len(order_late),
        "total_reviews_received": len(review_received),
        "total_returns_received": len(return_received),
        "total_resolved":        len(return_resolved),
        "total_products_listed": len(product_listed),
        "meaningful_event_count": meaningful_event_count,
        "total_event_count":     len(events),
        "recent_deliveries_30d": recent_deliveries,
        "recent_late_30d":       recent_late,
        "account_age_days":      account_age_days,

        "role": "seller",
    }


# ── Public dispatcher ─────────────────────────────────────────────────────────

def build_features(
    events: EventList,
    role: str,
    *,
    reference_ts: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Route to the correct role-specific builder.
    `role` must be 'buyer' or 'seller'.
    """
    if role == "buyer":
        return build_buyer_features(events, reference_ts=reference_ts)
    elif role == "seller":
        return build_seller_features(events, reference_ts=reference_ts)
    else:
        raise ValueError(f"Unknown role: {role!r}")


# ── Internal helpers ──────────────────────────────────────────────────────────

def _filter(events: EventList, event_type: str) -> EventList:
    return [e for e in events if e.get("event_type") == event_type]


def _age(event: Dict[str, Any], reference_ts: datetime) -> float:
    """Return age in days; handle both datetime objects and ISO strings."""
    ts = event.get("created_at")
    if ts is None:
        return 0.0
    if isinstance(ts, str):
        ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return event_age_days(ts, reference_ts)


def _meta(event: Dict[str, Any]) -> Dict[str, Any]:
    """Return the metadata dict from an event, or {}."""
    return event.get("metadata_") or event.get("metadata") or {}


def _account_age(events: EventList, reference_ts: datetime) -> float:
    """Days between the oldest event and the reference timestamp."""
    if not events:
        return 0.0
    ages = [_age(e, reference_ts) for e in events]
    return max(ages) if ages else 0.0
