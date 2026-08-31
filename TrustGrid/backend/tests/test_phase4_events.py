"""
Phase 4 tests — Event System.
Verifies that every marketplace action fires the correct TrustGrid events.
Uses in-memory SQLite.
"""
import pytest
import random
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.trustgrid.event_types import EventType, MEANINGFUL_EVENTS, NEGATIVE_EVENTS
from app.trustgrid.event_service import (
    record_event, record_events_batch,
    get_events_for_user, count_meaningful_events,
)
from app.services.user_service import create_user
from app.services.product_service import create_product
from app.services.order_service import (
    place_order, cancel_order, ship_order, complete_order,
    request_return, submit_review, resolve_return,
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
        title="Widget", price=Decimal("99.99"), stock=50,
    ))


def _force_paid_order(db, buyer, product):
    """Place order and force it to paid status for deterministic tests."""
    random.seed(42)
    order = place_order(db, buyer.user_id, OrderCreate(product_id=product.id, quantity=1))
    if order.status != "paid":
        from app.models.marketplace import OrderStatus
        order.status = OrderStatus.paid
        db.commit(); db.refresh(order)
    return order


# ── Event type enum tests ─────────────────────────────────────────────────────

class TestEventTypes:
    def test_all_buyer_events_defined(self):
        for et in [
            EventType.ORDER_PLACED, EventType.ORDER_COMPLETED, EventType.ORDER_CANCELLED,
            EventType.PAYMENT_SUCCESS, EventType.PAYMENT_FAILED,
            EventType.RETURN_REQUESTED, EventType.RETURN_COMPLETED,
            EventType.REVIEW_SUBMITTED, EventType.REFERRAL_COMPLETED,
        ]:
            assert et.value is not None

    def test_all_seller_events_defined(self):
        for et in [
            EventType.ORDER_FULFILLED, EventType.ORDER_DELIVERED, EventType.ORDER_LATE,
            EventType.SELLER_CANCELLED, EventType.RETURN_REQUEST_RECEIVED,
            EventType.RETURN_RESOLVED, EventType.RETURN_REJECTED,
            EventType.REVIEW_RECEIVED, EventType.PRODUCT_LISTED,
        ]:
            assert et.value is not None

    def test_meaningful_events_non_empty(self):
        assert len(MEANINGFUL_EVENTS) > 0

    def test_negative_events_non_empty(self):
        assert len(NEGATIVE_EVENTS) > 0

    def test_meaningful_and_negative_no_overlap(self):
        overlap = MEANINGFUL_EVENTS & NEGATIVE_EVENTS
        assert len(overlap) == 0, f"Overlap found: {overlap}"


# ── Record event tests ────────────────────────────────────────────────────────

class TestRecordEvent:
    def test_record_single_event(self, db, buyer):
        ev = record_event(db, buyer.user_id, EventType.ORDER_PLACED, reference_id="ORD-001")
        assert ev.id is not None
        assert ev.event_id.startswith("EVT-")
        assert ev.event_type == EventType.ORDER_PLACED.value
        assert ev.user_id == buyer.user_id
        assert ev.reference_id == "ORD-001"

    def test_event_id_is_unique(self, db, buyer):
        ev1 = record_event(db, buyer.user_id, EventType.ORDER_PLACED)
        ev2 = record_event(db, buyer.user_id, EventType.ORDER_PLACED)
        assert ev1.event_id != ev2.event_id

    def test_record_events_batch(self, db, buyer, seller):
        events = record_events_batch(db, [
            {"user_id": buyer.user_id,  "event_type": EventType.ORDER_COMPLETED},
            {"user_id": seller.user_id, "event_type": EventType.ORDER_DELIVERED},
        ])
        assert len(events) == 2
        assert events[0].user_id == buyer.user_id
        assert events[1].user_id == seller.user_id

    def test_get_events_for_user(self, db, buyer):
        record_event(db, buyer.user_id, EventType.ORDER_PLACED)
        record_event(db, buyer.user_id, EventType.PAYMENT_SUCCESS)
        evs = get_events_for_user(db, buyer.user_id)
        assert len(evs) == 2

    def test_events_are_user_scoped(self, db, buyer, seller):
        record_event(db, buyer.user_id,  EventType.ORDER_PLACED)
        record_event(db, seller.user_id, EventType.ORDER_FULFILLED)
        buyer_evs  = get_events_for_user(db, buyer.user_id)
        seller_evs = get_events_for_user(db, seller.user_id)
        assert len(buyer_evs)  == 1
        assert len(seller_evs) == 1


# ── Marketplace → events integration ─────────────────────────────────────────

class TestOrderEvents:
    def test_place_order_fires_order_placed(self, db, buyer, product):
        random.seed(42)
        place_order(db, buyer.user_id, OrderCreate(product_id=product.id, quantity=1))
        evs = get_events_for_user(db, buyer.user_id)
        types = [e.event_type for e in evs]
        assert EventType.ORDER_PLACED.value in types

    def test_place_order_fires_payment_event(self, db, buyer, product):
        random.seed(42)
        place_order(db, buyer.user_id, OrderCreate(product_id=product.id, quantity=1))
        evs = get_events_for_user(db, buyer.user_id)
        types = [e.event_type for e in evs]
        assert (
            EventType.PAYMENT_SUCCESS.value in types or
            EventType.PAYMENT_FAILED.value in types
        )

    def test_cancel_by_buyer_fires_order_cancelled(self, db, buyer, product):
        order = _force_paid_order(db, buyer, product)
        cancel_order(db, order.order_id, buyer.user_id, "buyer")
        evs = get_events_for_user(db, buyer.user_id)
        types = [e.event_type for e in evs]
        assert EventType.ORDER_CANCELLED.value in types

    def test_cancel_by_seller_fires_seller_cancelled(self, db, buyer, seller, product):
        order = _force_paid_order(db, buyer, product)
        cancel_order(db, order.order_id, seller.user_id, "seller")
        seller_evs = get_events_for_user(db, seller.user_id)
        types = [e.event_type for e in seller_evs]
        assert EventType.SELLER_CANCELLED.value in types

    def test_ship_fires_order_fulfilled_for_seller(self, db, buyer, seller, product):
        order = _force_paid_order(db, buyer, product)
        ship_order(db, order.order_id, seller.user_id)
        seller_evs = get_events_for_user(db, seller.user_id)
        types = [e.event_type for e in seller_evs]
        assert EventType.ORDER_FULFILLED.value in types

    def test_complete_fires_completed_for_buyer(self, db, buyer, seller, product):
        order = _force_paid_order(db, buyer, product)
        ship_order(db, order.order_id, seller.user_id)
        complete_order(db, order.order_id, buyer.user_id)
        buyer_evs = get_events_for_user(db, buyer.user_id)
        types = [e.event_type for e in buyer_evs]
        assert EventType.ORDER_COMPLETED.value in types

    def test_complete_fires_delivered_for_seller(self, db, buyer, seller, product):
        order = _force_paid_order(db, buyer, product)
        ship_order(db, order.order_id, seller.user_id)
        complete_order(db, order.order_id, buyer.user_id)
        seller_evs = get_events_for_user(db, seller.user_id)
        types = [e.event_type for e in seller_evs]
        assert EventType.ORDER_DELIVERED.value in types

    def test_return_fires_events_for_both(self, db, buyer, seller, product):
        order = _force_paid_order(db, buyer, product)
        ship_order(db, order.order_id, seller.user_id)
        complete_order(db, order.order_id, buyer.user_id)
        request_return(db, order.order_id, buyer.user_id, ReturnCreate(reason="Wrong item"))

        buyer_types  = [e.event_type for e in get_events_for_user(db, buyer.user_id)]
        seller_types = [e.event_type for e in get_events_for_user(db, seller.user_id)]
        assert EventType.RETURN_REQUESTED.value in buyer_types
        assert EventType.RETURN_REQUEST_RECEIVED.value in seller_types

    def test_review_fires_events_for_both(self, db, buyer, seller, product):
        order = _force_paid_order(db, buyer, product)
        ship_order(db, order.order_id, seller.user_id)
        complete_order(db, order.order_id, buyer.user_id)
        submit_review(db, order.order_id, buyer.user_id, ReviewCreate(rating=5))

        buyer_types  = [e.event_type for e in get_events_for_user(db, buyer.user_id)]
        seller_types = [e.event_type for e in get_events_for_user(db, seller.user_id)]
        assert EventType.REVIEW_SUBMITTED.value in buyer_types
        assert EventType.REVIEW_RECEIVED.value in seller_types

    def test_review_metadata_contains_rating(self, db, buyer, seller, product):
        order = _force_paid_order(db, buyer, product)
        ship_order(db, order.order_id, seller.user_id)
        complete_order(db, order.order_id, buyer.user_id)
        submit_review(db, order.order_id, buyer.user_id, ReviewCreate(rating=4))

        buyer_evs = get_events_for_user(db, buyer.user_id)
        review_ev = next(e for e in buyer_evs if e.event_type == EventType.REVIEW_SUBMITTED.value)
        assert review_ev.metadata_["rating"] == 4

    def test_resolve_return_fires_resolved(self, db, buyer, seller, product):
        order = _force_paid_order(db, buyer, product)
        ship_order(db, order.order_id, seller.user_id)
        complete_order(db, order.order_id, buyer.user_id)
        ret = request_return(db, order.order_id, buyer.user_id, ReturnCreate())
        resolve_return(db, ret.id, seller.user_id, "resolved")

        seller_types = [e.event_type for e in get_events_for_user(db, seller.user_id)]
        buyer_types  = [e.event_type for e in get_events_for_user(db, buyer.user_id)]
        assert EventType.RETURN_RESOLVED.value in seller_types
        assert EventType.RETURN_COMPLETED.value in buyer_types

    def test_reject_return_fires_rejected(self, db, buyer, seller, product):
        order = _force_paid_order(db, buyer, product)
        ship_order(db, order.order_id, seller.user_id)
        complete_order(db, order.order_id, buyer.user_id)
        ret = request_return(db, order.order_id, buyer.user_id, ReturnCreate())
        resolve_return(db, ret.id, seller.user_id, "rejected")

        seller_types = [e.event_type for e in get_events_for_user(db, seller.user_id)]
        assert EventType.RETURN_REJECTED.value in seller_types


# ── Product events ────────────────────────────────────────────────────────────

class TestProductEvents:
    def test_create_product_fires_product_listed(self, db, seller):
        create_product(db, seller.user_id, ProductCreate(
            title="New Product", price=Decimal("49.00"), stock=10,
        ))
        seller_evs = get_events_for_user(db, seller.user_id)
        types = [e.event_type for e in seller_evs]
        assert EventType.PRODUCT_LISTED.value in types


# ── Confidence count tests ────────────────────────────────────────────────────

class TestConfidenceCount:
    def test_new_user_has_zero_meaningful_events(self, db, buyer):
        count = count_meaningful_events(db, buyer.user_id)
        assert count == 0

    def test_completed_order_increments_meaningful_count(self, db, buyer, seller, product):
        order = _force_paid_order(db, buyer, product)
        ship_order(db, order.order_id, seller.user_id)
        complete_order(db, order.order_id, buyer.user_id)
        count = count_meaningful_events(db, buyer.user_id)
        # ORDER_COMPLETED + PAYMENT_SUCCESS = 2 meaningful events
        assert count >= 2

    def test_cancelled_order_does_not_increment_meaningful_count(self, db, buyer, product):
        order = _force_paid_order(db, buyer, product)
        cancel_order(db, order.order_id, buyer.user_id, "buyer")
        # PAYMENT_SUCCESS is meaningful, ORDER_CANCELLED is not
        count = count_meaningful_events(db, buyer.user_id)
        # Only PAYMENT_SUCCESS should count
        assert count == 1
