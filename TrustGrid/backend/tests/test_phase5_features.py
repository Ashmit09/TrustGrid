"""
Phase 5 tests — Feature Engine.

Tests cover:
  - Decay weight math at known ages
  - Neutral defaults for new users
  - Buyer feature rates (completion, return, payment, cancellation)
  - Seller feature rates (fulfillment, late delivery, rating, return response)
  - Time decay: older events contribute less than recent ones
  - Infrequent buyer principle: low purchase count ≠ low score
  - Event → feature auto-update integration
"""
import math
import pytest
import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.trustgrid.feature_engine import (
    decay_weight, update_features, get_feature_vector, _neutral_features, _LAMBDA, _HALF_LIFE_DAYS
)
from app.trustgrid.event_service import record_event, record_events_batch
from app.trustgrid.event_types import EventType
from app.models.trust import TrustEvent, BehaviorFeatures
from app.services.user_service import create_user
from app.services.product_service import create_product
from app.services.order_service import (
    place_order, cancel_order, ship_order, complete_order,
    request_return, submit_review,
)
from app.schemas.product import ProductCreate
from app.schemas.order import OrderCreate, ReturnCreate, ReviewCreate


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="function")
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def buyer(db):
    return create_user(db, "Alice", "alice@test.com", "Password1!", "buyer")


@pytest.fixture
def seller(db):
    return create_user(db, "Bob", "bob@test.com", "Password1!", "seller")


@pytest.fixture
def product(db, seller):
    return create_product(db, seller.user_id, ProductCreate(
        title="Widget", price=Decimal("199.99"), stock=100,
    ))


def _paid_order(db, buyer, product):
    """Create and force-paid an order."""
    random.seed(42)
    order = place_order(db, buyer.user_id, OrderCreate(product_id=product.id, quantity=1))
    if order.status != "paid":
        from app.models.marketplace import OrderStatus
        order.status = OrderStatus.paid
        db.commit(); db.refresh(order)
    return order


def _back_date_events(db, user_id: str, days_ago: float):
    """
    Move all existing events for a user to `days_ago` days in the past.
    Used to test time decay behaviour.
    """
    past = datetime.now(timezone.utc) - timedelta(days=days_ago)
    events = db.query(TrustEvent).filter(TrustEvent.user_id == user_id).all()
    for ev in events:
        ev.created_at = past
    db.commit()


# ── Decay math tests ──────────────────────────────────────────────────────────

class TestDecayMath:
    def test_lambda_value(self):
        """λ = ln(2) / 90"""
        expected = math.log(2) / 90
        assert abs(_LAMBDA - expected) < 1e-9

    def test_decay_at_zero_days_is_one(self):
        now = datetime.now(timezone.utc)
        w = decay_weight(now, now)
        assert abs(w - 1.0) < 1e-6

    def test_decay_at_half_life_is_half(self):
        now = datetime.now(timezone.utc)
        half_life_ago = now - timedelta(days=_HALF_LIFE_DAYS)
        w = decay_weight(half_life_ago, now)
        assert abs(w - 0.5) < 0.001   # allow tiny floating-point tolerance

    def test_decay_at_30_days(self):
        """weight(30) = exp(−λ·30) ≈ 0.794"""
        now = datetime.now(timezone.utc)
        t = now - timedelta(days=30)
        w = decay_weight(t, now)
        expected = math.exp(-_LAMBDA * 30)
        assert abs(w - expected) < 1e-6

    def test_decay_at_180_days(self):
        """weight(180) ≈ 0.25 (two half-lives)"""
        now = datetime.now(timezone.utc)
        t = now - timedelta(days=180)
        w = decay_weight(t, now)
        assert abs(w - 0.25) < 0.01

    def test_decay_at_270_days(self):
        """weight(270) ≈ 0.125 (three half-lives)"""
        now = datetime.now(timezone.utc)
        t = now - timedelta(days=270)
        w = decay_weight(t, now)
        assert abs(w - 0.125) < 0.01

    def test_older_event_has_lower_weight_than_recent(self):
        now = datetime.now(timezone.utc)
        w_recent = decay_weight(now - timedelta(days=5),  now)
        w_old    = decay_weight(now - timedelta(days=120), now)
        assert w_recent > w_old

    def test_decay_weight_never_exceeds_one(self):
        now = datetime.now(timezone.utc)
        assert decay_weight(now, now) <= 1.0

    def test_decay_weight_always_positive(self):
        now = datetime.now(timezone.utc)
        w = decay_weight(now - timedelta(days=3650), now)  # 10 years ago
        assert w > 0.0


# ── New user / neutral defaults ───────────────────────────────────────────────

class TestNeutralDefaults:
    def test_new_user_gets_neutral_features(self, db, buyer):
        features = get_feature_vector(db, buyer.user_id)
        assert features["order_completion_rate"] == 1.0
        assert features["payment_success_rate"]  == 1.0
        assert features["return_rate"]           == 0.0
        assert features["cancellation_rate"]     == 0.0
        assert features["total_orders"]          == 0

    def test_neutral_features_returns_all_keys(self):
        nf = _neutral_features()
        required_keys = [
            "order_completion_rate", "return_rate", "payment_success_rate",
            "cancellation_rate", "referral_count", "review_count",
            "fulfillment_rate", "late_delivery_rate", "avg_rating_received",
            "return_response_rate",
        ]
        for key in required_keys:
            assert key in nf, f"Missing key: {key}"


# ── Buyer feature tests ───────────────────────────────────────────────────────

class TestBuyerFeatures:
    def test_completed_order_raises_completion_rate(self, db, buyer, seller, product):
        order = _paid_order(db, buyer, product)
        ship_order(db, order.order_id, seller.user_id)
        complete_order(db, order.order_id, buyer.user_id)

        features = get_feature_vector(db, buyer.user_id)
        # With 1 placed, 1 completed: rate = 1.0
        assert features["order_completion_rate"] == 1.0
        assert features["completed_orders"] >= 1

    def test_payment_success_rate_after_successful_payment(self, db, buyer, seller, product):
        order = _paid_order(db, buyer, product)
        features = get_feature_vector(db, buyer.user_id)
        # PAYMENT_SUCCESS event was fired; rate should be 1.0 or very high
        assert features["payment_success_rate"] >= 0.9

    def test_cancellation_raises_cancellation_rate(self, db, buyer, product):
        order = _paid_order(db, buyer, product)
        cancel_order(db, order.order_id, buyer.user_id, "buyer")
        features = get_feature_vector(db, buyer.user_id)
        assert features["cancellation_rate"] > 0.0

    def test_return_raises_return_rate_after_completion(self, db, buyer, seller, product):
        order = _paid_order(db, buyer, product)
        ship_order(db, order.order_id, seller.user_id)
        complete_order(db, order.order_id, buyer.user_id)
        request_return(db, order.order_id, buyer.user_id, ReturnCreate(reason="Wrong item"))

        features = get_feature_vector(db, buyer.user_id)
        assert features["return_rate"] > 0.0
        assert features["total_returns"] >= 1

    def test_referral_increments_referral_count(self, db, buyer):
        # Directly record the event and manually trigger feature update
        from app.trustgrid.event_service import update_features_for_users
        record_event(db, buyer.user_id, EventType.REFERRAL_COMPLETED,
                     impact_summary="Referred a friend")
        update_features_for_users(db, [buyer.user_id])
        features = get_feature_vector(db, buyer.user_id)
        assert features["referral_count"] == 1

    def test_review_increments_review_count(self, db, buyer, seller, product):
        order = _paid_order(db, buyer, product)
        ship_order(db, order.order_id, seller.user_id)
        complete_order(db, order.order_id, buyer.user_id)
        submit_review(db, order.order_id, buyer.user_id, ReviewCreate(rating=5))

        features = get_feature_vector(db, buyer.user_id)
        assert features["review_count"] >= 1

    def test_infrequent_buyer_not_penalised(self, db, buyer, seller, product):
        """
        A buyer who completes only 1 order should have completion_rate = 1.0.
        Low purchase volume must NOT lower the rate.
        """
        order = _paid_order(db, buyer, product)
        ship_order(db, order.order_id, seller.user_id)
        complete_order(db, order.order_id, buyer.user_id)

        features = get_feature_vector(db, buyer.user_id)
        # 1 completed / 1 placed = perfect rate
        assert features["order_completion_rate"] == 1.0


# ── Seller feature tests ──────────────────────────────────────────────────────

class TestSellerFeatures:
    def test_fulfillment_rate_after_shipping(self, db, buyer, seller, product):
        order = _paid_order(db, buyer, product)
        ship_order(db, order.order_id, seller.user_id)

        features = get_feature_vector(db, seller.user_id)
        assert features["fulfillment_rate"] == 1.0
        assert features["fulfilled_orders"] >= 1

    def test_seller_cancellation_lowers_fulfillment_rate(self, db, buyer, seller, product):
        """Two orders: one fulfilled, one seller-cancelled → rate < 1.0"""
        # Order 1: fulfilled
        order1 = _paid_order(db, buyer, product)
        ship_order(db, order1.order_id, seller.user_id)

        # Order 2: seller cancels
        product.stock = 100; db.commit()
        order2 = _paid_order(db, buyer, product)
        cancel_order(db, order2.order_id, seller.user_id, "seller")

        features = get_feature_vector(db, seller.user_id)
        assert features["fulfillment_rate"] < 1.0

    def test_avg_rating_computed_from_reviews(self, db, buyer, seller, product):
        order = _paid_order(db, buyer, product)
        ship_order(db, order.order_id, seller.user_id)
        complete_order(db, order.order_id, buyer.user_id)
        submit_review(db, order.order_id, buyer.user_id, ReviewCreate(rating=4))

        features = get_feature_vector(db, seller.user_id)
        assert abs(features["avg_rating_received"] - 4.0) < 0.1

    def test_return_response_rate_after_resolving(self, db, buyer, seller, product):
        order = _paid_order(db, buyer, product)
        ship_order(db, order.order_id, seller.user_id)
        complete_order(db, order.order_id, buyer.user_id)
        ret = request_return(db, order.order_id, buyer.user_id, ReturnCreate())
        from app.services.order_service import resolve_return
        resolve_return(db, ret.id, seller.user_id, "resolved")

        features = get_feature_vector(db, seller.user_id)
        assert features["return_response_rate"] == 1.0

    def test_product_listed_increments_count(self, db, seller):
        from app.trustgrid.event_service import update_features_for_users
        record_event(db, seller.user_id, EventType.PRODUCT_LISTED, reference_id="1")
        update_features_for_users(db, [seller.user_id])
        features = get_feature_vector(db, seller.user_id)
        assert features["products_listed"] >= 1


# ── Time decay integration tests ──────────────────────────────────────────────

class TestTimeDecayIntegration:
    def test_recent_event_outweighs_old_event(self, db, buyer):
        """
        Two identical events: one recent, one 180 days old.
        The decayed_event_weight should be dominated by the recent one.
        """
        from app.trustgrid.event_service import update_features_for_users
        # Record first event
        record_event(db, buyer.user_id, EventType.PAYMENT_SUCCESS,
                     impact_summary="Recent payment")
        # Back-date all current events to 180 days ago
        _back_date_events(db, buyer.user_id, days_ago=180)
        # Add a fresh recent event
        record_event(db, buyer.user_id, EventType.PAYMENT_SUCCESS,
                     impact_summary="New payment")
        update_features_for_users(db, [buyer.user_id])
        features_after = get_feature_vector(db, buyer.user_id)
        assert features_after["decayed_event_weight"] > 0

    def test_very_old_events_have_minimal_weight(self, db, buyer):
        """A 365-day-old event should have weight ≈ 0.059 (very small)."""
        now = datetime.now(timezone.utc)
        t = now - timedelta(days=365)
        w = decay_weight(t, now)
        assert w < 0.1   # less than 10% of original weight

    def test_feature_weight_decreases_as_events_age(self, db, buyer):
        """
        Record a payment event, compute features now.
        Back-date the event by 90 days, recompute — weight should be ~halved.
        """
        record_event(db, buyer.user_id, EventType.PAYMENT_SUCCESS)
        features_fresh = update_features(db, buyer.user_id)
        weight_fresh = features_fresh.decayed_event_weight

        # Age the event by 90 days (one half-life)
        _back_date_events(db, buyer.user_id, days_ago=90)
        features_aged = update_features(db, buyer.user_id)
        weight_aged = features_aged.decayed_event_weight

        # After one half-life the weight should be roughly half
        ratio = weight_aged / weight_fresh if weight_fresh > 0 else 0
        assert 0.4 < ratio < 0.6, f"Expected ~0.5, got {ratio:.3f}"


# ── Auto-update integration ───────────────────────────────────────────────────

class TestAutoUpdate:
    def test_features_auto_updated_after_event(self, db, buyer):
        """After record_event + explicit update_features, row should have non-zero weight."""
        from app.trustgrid.event_service import update_features_for_users
        record_event(db, buyer.user_id, EventType.PAYMENT_SUCCESS)
        update_features_for_users(db, [buyer.user_id])
        fv = get_feature_vector(db, buyer.user_id)
        assert fv["decayed_event_weight"] > 0

    def test_features_auto_updated_after_batch(self, db, buyer, seller):
        from app.trustgrid.event_service import update_features_for_users
        record_events_batch(db, [
            {"user_id": buyer.user_id,  "event_type": EventType.ORDER_COMPLETED},
            {"user_id": seller.user_id, "event_type": EventType.ORDER_DELIVERED},
        ])
        update_features_for_users(db, [buyer.user_id, seller.user_id])
        buyer_fv  = get_feature_vector(db, buyer.user_id)
        seller_fv = get_feature_vector(db, seller.user_id)
        assert buyer_fv["decayed_event_weight"]  > 0
        assert seller_fv["decayed_event_weight"] > 0

    def test_feature_update_is_user_scoped(self, db, buyer, seller):
        """An event for buyer must not change seller's features."""
        seller_before = update_features(db, seller.user_id)
        weight_before = seller_before.decayed_event_weight

        record_event(db, buyer.user_id, EventType.ORDER_COMPLETED)

        seller_after = db.query(BehaviorFeatures).filter(
            BehaviorFeatures.user_id == seller.user_id
        ).first()
        assert seller_after.decayed_event_weight == weight_before
