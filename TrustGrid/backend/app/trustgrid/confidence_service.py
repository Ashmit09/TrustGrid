"""
TrustGrid Confidence Service.

Confidence answers the question:
    "How much behavioral evidence does TrustGrid have for this score?"

It is NOT a measure of whether a person is good or bad.
A brand-new user can have a perfectly legitimate 700 score but LOW confidence
because TrustGrid has almost no evidence yet.

Levels
------
LOW    → 0–5  meaningful completed transactions
MEDIUM → 6–30 meaningful completed transactions
HIGH   → 31+  meaningful completed transactions

"Meaningful" events are defined in event_types.MEANINGFUL_EVENTS.
The count is read from the trust_events table directly (not decayed –
evidence history counts permanently toward confidence).

Additionally, account age provides a secondary boost:
  - If the user has 4+ meaningful events AND the account is ≥ 30 days old,
    they can reach MEDIUM earlier.
  - This prevents brand-new accounts from rapidly faking high confidence.

The calculation is intentionally deterministic and explainable.
"""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.models.trust import ConfidenceLevel
from app.trustgrid.event_types import MEANINGFUL_EVENTS


def calculate_confidence(
    db: Session,
    user_id: str,
    account_created_at: Optional[datetime] = None,
) -> ConfidenceLevel:
    """
    Determine confidence level for a user based on evidence count and account age.

    Parameters
    ----------
    db               : active database session
    user_id          : the user's logical ID (BUY-xxxxx / SEL-xxxxx)
    account_created_at : user.created_at — used for age-based modifier

    Returns
    -------
    ConfidenceLevel.LOW | .MEDIUM | .HIGH
    """
    meaningful_count = _count_meaningful_events(db, user_id)

    # Primary thresholds
    if meaningful_count >= 31:
        return ConfidenceLevel.HIGH

    if meaningful_count >= 6:
        return ConfidenceLevel.MEDIUM

    # Soft-boost: 4-5 events on a ≥30-day-old account → MEDIUM
    if meaningful_count >= 4 and account_created_at is not None:
        account_age_days = _account_age_days(account_created_at)
        if account_age_days >= 30:
            return ConfidenceLevel.MEDIUM

    return ConfidenceLevel.LOW


def _count_meaningful_events(db: Session, user_id: str) -> int:
    """
    Count the total number of MEANINGFUL_EVENTS recorded for this user.
    Uses raw SQL to avoid any caching issues.
    """
    meaningful_values = tuple(e.value for e in MEANINGFUL_EVENTS)

    # Build a safe parameterised IN clause
    placeholders = ", ".join(f":evt_{i}" for i in range(len(meaningful_values)))
    params = {f"evt_{i}": v for i, v in enumerate(meaningful_values)}
    params["uid"] = user_id

    result = db.execute(
        text(f"""
            SELECT COUNT(*) FROM trust_events
            WHERE user_id = :uid
              AND event_type IN ({placeholders})
        """),
        params,
    ).scalar()
    return int(result or 0)


def _account_age_days(created_at: datetime) -> float:
    """Return how many days old the account is."""
    now = datetime.now(timezone.utc)
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return max(0.0, (now - created_at).total_seconds() / 86_400)
