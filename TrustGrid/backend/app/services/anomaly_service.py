"""
Anomaly Detection Service.

Scans recent score history and behavioral features for suspicious
patterns and creates AnomalyFlag records.

Patterns detected
-----------------
SCORE_DROP          → trust_score fell by >=150 pts within 24 h
SCORE_SURGE         → trust_score rose by >=200 pts within 24 h
RAPID_CANCELLATIONS → cancellation_rate > 0.6 AND total_cancellations >= 3
HIGH_RETURN_RATE    → return_rate > 0.5 AND total_returns >= 3
"""
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.models.trust import ScoreHistory, AnomalyFlag
from app.models.user import User
from app.models.trust import BehaviorFeatures


_SCORE_DROP_THRESHOLD  = 150   # points
_SCORE_SURGE_THRESHOLD = 200   # points
_WINDOW_HOURS          = 24
_CANCEL_RATE_THRESHOLD = 0.60
_CANCEL_MIN_EVENTS     = 3
_RETURN_RATE_THRESHOLD = 0.50
_RETURN_MIN_EVENTS     = 3


def _already_flagged(db: Session, user_id: str, flag_type: str, since: datetime) -> bool:
    """Return True if an open flag of this type already exists within the window."""
    return db.query(AnomalyFlag).filter(
        AnomalyFlag.user_id   == user_id,
        AnomalyFlag.flag_type == flag_type,
        AnomalyFlag.resolved  == 0,
        AnomalyFlag.created_at >= since,
    ).first() is not None


def _create_flag(
    db: Session,
    user_id: str,
    flag_type: str,
    severity: str,
    description: str,
    score_before: Optional[int] = None,
    score_after:  Optional[int] = None,
) -> AnomalyFlag:
    flag = AnomalyFlag(
        flag_id      = str(uuid.uuid4()),
        user_id      = user_id,
        flag_type    = flag_type,
        severity     = severity,
        description  = description,
        score_before = score_before,
        score_after  = score_after,
        resolved     = 0,
        created_at   = datetime.now(timezone.utc),
    )
    db.add(flag)
    db.commit()
    db.refresh(flag)
    return flag


def run_anomaly_scan(db: Session) -> list:
    """
    Scan all users for anomalous patterns.
    Returns a list of newly created AnomalyFlag rows.
    Returns an empty list if no new anomalies are found.
    """
    now    = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=_WINDOW_HOURS)
    new_flags: list[AnomalyFlag] = []

    users = db.query(User).filter(User.role != "admin").all()

    for user in users:
        uid = user.user_id

        # ── 1. Score-change patterns (24h window) ───────────────────────
        recent = (
            db.query(ScoreHistory)
            .filter(ScoreHistory.user_id == uid, ScoreHistory.created_at >= cutoff)
            .order_by(ScoreHistory.created_at.asc())
            .all()
        )

        if len(recent) >= 2:
            oldest_score = recent[0].old_score
            newest_score = recent[-1].new_score
            delta = newest_score - oldest_score

            if delta <= -_SCORE_DROP_THRESHOLD:
                if not _already_flagged(db, uid, "SCORE_DROP", cutoff):
                    new_flags.append(_create_flag(
                        db, uid, "SCORE_DROP", "HIGH",
                        f"Score dropped {abs(delta)} pts in 24 h ({oldest_score} → {newest_score}).",
                        score_before=oldest_score, score_after=newest_score,
                    ))

            elif delta >= _SCORE_SURGE_THRESHOLD:
                if not _already_flagged(db, uid, "SCORE_SURGE", cutoff):
                    new_flags.append(_create_flag(
                        db, uid, "SCORE_SURGE", "MEDIUM",
                        f"Score surged +{delta} pts in 24 h ({oldest_score} → {newest_score}).",
                        score_before=oldest_score, score_after=newest_score,
                    ))

        # ── 2. Behavioural feature patterns ─────────────────────────────
        bf = db.query(BehaviorFeatures).filter(BehaviorFeatures.user_id == uid).first()
        if bf is None:
            continue

        if (bf.cancellation_rate > _CANCEL_RATE_THRESHOLD
                and bf.total_cancellations >= _CANCEL_MIN_EVENTS):
            if not _already_flagged(db, uid, "RAPID_CANCELLATIONS", cutoff):
                new_flags.append(_create_flag(
                    db, uid, "RAPID_CANCELLATIONS", "HIGH",
                    f"Cancellation rate {bf.cancellation_rate:.0%} "
                    f"across {bf.total_cancellations} orders.",
                ))

        if (bf.return_rate > _RETURN_RATE_THRESHOLD
                and bf.total_returns >= _RETURN_MIN_EVENTS):
            if not _already_flagged(db, uid, "HIGH_RETURN_RATE", cutoff):
                new_flags.append(_create_flag(
                    db, uid, "HIGH_RETURN_RATE", "MEDIUM",
                    f"Return rate {bf.return_rate:.0%} "
                    f"across {bf.total_returns} returns.",
                ))

    return new_flags
