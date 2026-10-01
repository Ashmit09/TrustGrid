"""
TrustGrid — Time Decay Engine

Frozen formula (spec §7):
    w(t) = e^(−λ·t)   where λ = ln(2)/90 ≈ 0.007701

This module is the single source of decay mathematics.
All dimensions MUST call decay_weight() / decayed_rate() from here.
Do NOT compute decay anywhere else.
"""
import math
from datetime import datetime, timezone
from typing import Sequence, Tuple

from app.core.constants import DECAY_LAMBDA


def decay_weight(age_days: float) -> float:
    """
    Return the exponential decay weight for an event that is `age_days` old.

    w = e^(−λ · age_days)

    age_days must be ≥ 0.  Negative values (future events) are clamped to 0.

    Reference values from spec:
        0 days   → 1.000
        7 days   → ≈ 0.947
        30 days  → ≈ 0.794
        60 days  → ≈ 0.630
        90 days  → 0.500
        180 days → 0.250
        270 days → 0.125
        360 days → ≈ 0.063
    """
    age_days = max(0.0, age_days)
    return math.exp(-DECAY_LAMBDA * age_days)


def event_age_days(event_ts: datetime, reference_ts: datetime) -> float:
    """
    Return the age of an event in fractional days relative to a reference time.

    Both datetimes should be timezone-aware (UTC).  If naive, UTC is assumed.
    """
    if event_ts.tzinfo is None:
        event_ts = event_ts.replace(tzinfo=timezone.utc)
    if reference_ts.tzinfo is None:
        reference_ts = reference_ts.replace(tzinfo=timezone.utc)
    delta = reference_ts - event_ts
    return max(0.0, delta.total_seconds() / 86_400.0)


def decayed_rate(
    events: Sequence[Tuple[float, int]],
    *,
    default_if_empty: float = 0.5,
) -> float:
    """
    Calculate a time-decayed ratio (0–1) from a sequence of (age_days, is_positive) tuples.

    Formula (spec §7):
        R = Σ(positive_i × w_i) / Σ(eligible_i × w_i)

    where:
        positive_i  = 1 if the event outcome is positive, 0 otherwise
        eligible_i  = 1 for every eligible event
        w_i         = decay_weight(age_i)

    Parameters
    ----------
    events          : sequence of (age_days, is_positive) tuples
                      is_positive = 1 for a positive outcome, 0 otherwise
    default_if_empty: value to return when there is no eligible evidence
                      (cold-start); default 0.5 → dimension starts at 50
                      until first evidence arrives.

    Returns
    -------
    Decayed rate in [0.0, 1.0].
    """
    if not events:
        return default_if_empty

    weighted_positive = 0.0
    weighted_total = 0.0

    for age_days, is_positive in events:
        w = decay_weight(age_days)
        weighted_total += w
        if is_positive:
            weighted_positive += w

    if weighted_total == 0.0:
        return default_if_empty

    rate = weighted_positive / weighted_total
    return max(0.0, min(1.0, rate))


def decayed_average(
    values: Sequence[Tuple[float, float]],
    *,
    default_if_empty: float = 0.0,
) -> float:
    """
    Calculate a time-decayed weighted average of numeric values.
    Used for seller customer-satisfaction (average rating).

    Parameters
    ----------
    values          : sequence of (age_days, numeric_value) tuples
    default_if_empty: returned when the sequence is empty.

    Returns
    -------
    Weighted average, NOT clamped (caller must normalise for the dimension).
    """
    if not values:
        return default_if_empty

    weighted_sum = 0.0
    weighted_total = 0.0

    for age_days, value in values:
        w = decay_weight(age_days)
        weighted_sum += w * value
        weighted_total += w

    if weighted_total == 0.0:
        return default_if_empty

    return weighted_sum / weighted_total
