"""
TrustGrid-specific ORM models:
  TrustEvent, BehaviorFeatures, TrustScore, ScoreHistory, Privilege, AnomalyFlag
"""
import enum
from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey, Enum, JSON
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class ConfidenceLevel(str, enum.Enum):
    LOW    = "LOW"
    MEDIUM = "MEDIUM"
    HIGH   = "HIGH"


class TrustTier(str, enum.Enum):
    RESTRICTED = "RESTRICTED"
    STANDARD   = "STANDARD"
    TRUSTED    = "TRUSTED"
    ELITE      = "ELITE"


class TrustEvent(Base):
    """One record per marketplace event that affects TrustGrid."""
    __tablename__ = "trust_events"

    id             = Column(Integer, primary_key=True, index=True)
    event_id       = Column(String(50), unique=True, nullable=False, index=True)
    user_id        = Column(String(20), ForeignKey("users.user_id"), nullable=False, index=True)
    event_type     = Column(String(60), nullable=False)
    reference_id   = Column(String(50), nullable=True)   # order_id / product_id etc.
    metadata_      = Column("metadata", JSON, nullable=True)
    impact_summary = Column(String(255), nullable=True)
    created_at     = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                            index=True)

    user = relationship("User", back_populates="trust_events")


class BehaviorFeatures(Base):
    """Aggregated, time-decayed behavioral feature vector for one user."""
    __tablename__ = "behavior_features"

    id   = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(20), ForeignKey("users.user_id"), unique=True, nullable=False, index=True)

    # Buyer features
    total_orders            = Column(Integer, default=0)
    completed_orders        = Column(Integer, default=0)
    order_completion_rate   = Column(Float, default=0.0)
    total_returns           = Column(Integer, default=0)
    return_rate             = Column(Float, default=0.0)
    payment_attempts        = Column(Integer, default=0)
    successful_payments     = Column(Integer, default=0)
    payment_success_rate    = Column(Float, default=1.0)
    total_cancellations     = Column(Integer, default=0)
    cancellation_rate       = Column(Float, default=0.0)
    referral_count          = Column(Integer, default=0)
    review_count            = Column(Integer, default=0)

    # Seller features
    fulfilled_orders        = Column(Integer, default=0)
    seller_cancellations    = Column(Integer, default=0)
    fulfillment_rate        = Column(Float, default=1.0)
    on_time_deliveries      = Column(Integer, default=0)
    late_deliveries         = Column(Integer, default=0)
    late_delivery_rate      = Column(Float, default=0.0)
    avg_rating_received     = Column(Float, default=0.0)
    return_requests_received = Column(Integer, default=0)
    returns_responded        = Column(Integer, default=0)
    return_response_rate    = Column(Float, default=1.0)
    products_listed         = Column(Integer, default=0)

    # Shared / decay meta
    decayed_event_weight    = Column(Float, default=0.0)
    updated_at              = Column(DateTime(timezone=True),
                                     default=lambda: datetime.now(timezone.utc),
                                     onupdate=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="behavior_features")


class TrustScore(Base):
    """Current TrustGrid state for one user (single live row)."""
    __tablename__ = "trust_scores"

    id           = Column(Integer, primary_key=True, index=True)
    user_id      = Column(String(20), ForeignKey("users.user_id"), unique=True, nullable=False, index=True)
    trust_score  = Column(Integer, default=700, nullable=False)
    confidence   = Column(Enum(ConfidenceLevel), default=ConfidenceLevel.LOW, nullable=False)
    tier         = Column(Enum(TrustTier), default=TrustTier.TRUSTED, nullable=False)
    # Stores per-dimension scores as JSON: {"order_reliability": 70, ...}
    dim_scores   = Column(JSON, nullable=True)
    last_updated = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                          onupdate=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="trust_score")


class ScoreHistory(Base):
    """Append-only log of every trust score change."""
    __tablename__ = "score_history"

    id           = Column(Integer, primary_key=True, index=True)
    user_id      = Column(String(20), ForeignKey("users.user_id"), nullable=False, index=True)
    old_score    = Column(Integer, nullable=False)
    new_score    = Column(Integer, nullable=False)
    score_change = Column(Integer, nullable=False)
    reason       = Column(String(255), nullable=True)
    event_type   = Column(String(60), nullable=True)
    created_at   = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                          index=True)

    user = relationship("User", back_populates="score_history")


class Privilege(Base):
    """Current privilege/benefit state for one user."""
    __tablename__ = "privileges"

    id             = Column(Integer, primary_key=True, index=True)
    user_id        = Column(String(20), ForeignKey("users.user_id"), nullable=False, index=True)
    privilege_name = Column(String(100), nullable=False)
    status         = Column(String(20), default="inactive", nullable=False)  # active | inactive
    reason         = Column(String(255), nullable=True)
    updated_at     = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                            onupdate=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="privileges")


class AnomalyFlag(Base):
    """
    Automatically generated alert when a user's trust score changes
    suspiciously (e.g., >150 pts drop within 24h, or a rapid surge of
    cancellations).  Flags are created by the anomaly detection service
    and surfaced in the Admin Alerts tab.
    """
    __tablename__ = "anomaly_flags"

    id            = Column(Integer, primary_key=True, index=True)
    flag_id       = Column(String(36), unique=True, nullable=False, index=True)
    user_id       = Column(String(20), ForeignKey("users.user_id"), nullable=False, index=True)
    flag_type     = Column(String(60), nullable=False)   # e.g. SCORE_DROP | RAPID_CANCELLATIONS | SCORE_SURGE
    severity      = Column(String(20), default="MEDIUM", nullable=False)  # LOW | MEDIUM | HIGH
    description   = Column(String(512), nullable=False)
    score_before  = Column(Integer, nullable=True)
    score_after   = Column(Integer, nullable=True)
    resolved      = Column(Integer, default=0, nullable=False)  # 0=open, 1=resolved (SQLite-safe bool)
    created_at    = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    resolved_at   = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="anomaly_flags")
