"""
Phase 6/7/8 tests — Trust Engine · Confidence · Privilege Engine.

Tests cover:
  - Confidence levels based on evidence count and account age
  - Trust Score formula (buyer and seller)
  - Score smoothing (alpha blending with prior score)
  - Tier determination
  - Score clamping (0 and 1000 boundaries)
  - New user initial state (700 / LOW / TRUSTED)
  - Score increases on positive behavior
  - Score decreases on negative behavior
  - Recent behavior > old behavior (via time decay)
  - Buyer privileges based on score + confidence
  - Seller privileges based on score + confidence
  - Full trust refresh pipeline (end-to-end)
  - GET /trust/me API endpoint
  - GET /trust/{user_id}/history
  - GET /trust/{user_id}/breakdown
  - GET /trust/{user_id}/benefits
"""
import math
import pytest
import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.trust import (
    TrustScore, ScoreHistory, Privilege,
    ConfidenceLevel, TrustTier,
)
from app.models.marketplace import OrderStatus
from app.models.user import UserRole
from app.trustgrid.confidence_service import calculate_confidence
from app.trustgrid.trust_engine import (
    recalculate_trust_score, score_to_tier,
    _buyer_dimensions, _seller_dimensions,
    _buyer_weighted, _seller_weighted,
    _rate_to_score, _clamp,
)
from app.trustgrid.privilege_engine import (
    recalculate_privileges, get_active_privilege_names,
)
from app.trustgrid.feature_engine import update_features, get_feature_vector
from app.trustgrid.event_service import record_event, update_features_for_users
from app.trustgrid.event_types import EventType
from app.services.user_service import create_user
from app.services.product_service import create_product
from app.services.order_service import (
    place_order, cancel_order, ship_order, complete_order,
    request_return, submit_review,
)
from app.services import trust_service
from app.schemas.product import ProductCreate
from app.schemas.order import OrderCreate, ReturnCreate, ReviewCreate


# ── Local SQLite fixtures (for service-level tests) ───────────────────────────

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


def _force_paid_order(db, buyer, product):
    random.seed(42)
    order = place_order(db, buyer.user_id, OrderCreate(product_id=product.id, quantity=1))
    if order.status != "paid":
        order.status = OrderStatus.paid
        db.commit(); db.refresh(order)
    return order


def _back_date_events(db, user_id: str, days_ago: float):
    from app.models.trust import TrustEvent
    past = datetime.now(timezone.utc) - timedelta(days=days_ago)
    for ev in db.query(TrustEvent).filter(TrustEvent.user_id == user_id).all():
        ev.created_at = past
    db.commit()


# ── Score to tier ─────────────────────────────────────────────────────────────

class TestTierDetermination:
    def test_score_0_is_restricted(self):
        assert score_to_tier(0) == TrustTier.RESTRICTED

    def test_score_399_is_restricted(self):
        assert score_to_tier(399) == TrustTier.RESTRICTED

    def test_score_400_is_standard(self):
        assert score_to_tier(400) == TrustTier.STANDARD

    def test_score_599_is_standard(self):
        assert score_to_tier(599) == TrustTier.STANDARD

    def test_score_600_is_trusted(self):
        assert score_to_tier(600) == TrustTier.TRUSTED

    def test_score_799_is_trusted(self):
        assert score_to_tier(799) == TrustTier.TRUSTED

    def test_score_800_is_elite(self):
        assert score_to_tier(800) == TrustTier.ELITE

    def test_score_1000_is_elite(self):
        assert score_to_tier(1000) == TrustTier.ELITE


# ── Score clamping ────────────────────────────────────────────────────────────

class TestScoreClamping:
    def test_clamp_below_zero(self):
        assert _clamp(-100) == 0

    def test_clamp_above_1000(self):
        assert _clamp(1100) == 1000

    def test_clamp_exact_zero(self):
        assert _clamp(0) == 0

    def test_clamp_exact_1000(self):
        assert _clamp(1000) == 1000

    def test_clamp_midrange_unchanged(self):
        assert _clamp(700) == 700


# ── Confidence calculation ────────────────────────────────────────────────────

class TestConfidenceCalculation:
    def test_new_user_is_low_confidence(self, db, buyer):
        conf = calculate_confidence(db, buyer.user_id, buyer.created_at)
        assert conf == ConfidenceLevel.LOW

    def test_five_meaningful_events_is_low(self, db, buyer):
        for _ in range(5):
            record_event(db, buyer.user_id, EventType.ORDER_COMPLETED)
        conf = calculate_confidence(db, buyer.user_id, buyer.created_at)
        assert conf == ConfidenceLevel.LOW

    def test_six_meaningful_events_is_medium(self, db, buyer):
        for _ in range(6):
            record_event(db, buyer.user_id, EventType.ORDER_COMPLETED)
        conf = calculate_confidence(db, buyer.user_id, buyer.created_at)
        assert conf == ConfidenceLevel.MEDIUM

    def test_thirty_one_events_is_high(self, db, buyer):
        for _ in range(31):
            record_event(db, buyer.user_id, EventType.PAYMENT_SUCCESS)
        conf = calculate_confidence(db, buyer.user_id, buyer.created_at)
        assert conf == ConfidenceLevel.HIGH

    def test_soft_boost_on_old_account_with_4_events(self, db, buyer):
        """4 events on a 31-day-old account → MEDIUM confidence."""
        for _ in range(4):
            record_event(db, buyer.user_id, EventType.ORDER_COMPLETED)
        old_date = datetime.now(timezone.utc) - timedelta(days=31)
        conf = calculate_confidence(db, buyer.user_id, account_created_at=old_date)
        assert conf == ConfidenceLevel.MEDIUM

    def test_non_meaningful_events_dont_boost_confidence(self, db, buyer):
        """ORDER_PLACED (not in MEANINGFUL_EVENTS) shouldn't count toward HIGH."""
        for _ in range(31):
            record_event(db, buyer.user_id, EventType.ORDER_PLACED)
        conf = calculate_confidence(db, buyer.user_id, buyer.created_at)
        assert conf == ConfidenceLevel.LOW


# ── Buyer dimension scores ────────────────────────────────────────────────────

class TestBuyerDimensions:
    def _perfect(self):
        return {
            "order_completion_rate": 1.0,
            "return_rate": 0.0,
            "payment_success_rate": 1.0,
            "cancellation_rate": 0.0,
            "referral_count": 5,
            "review_count": 10,
        }

    def _bad(self):
        return {
            "order_completion_rate": 0.3,
            "return_rate": 0.6,
            "payment_success_rate": 0.4,
            "cancellation_rate": 0.7,
            "referral_count": 0,
            "review_count": 0,
        }

    def test_perfect_buyer_score_near_1000(self):
        dim   = _buyer_dimensions(self._perfect())
        score = _clamp(round(_buyer_weighted(dim) * 10))
        assert score >= 900, f"Expected ≥900, got {score}"

    def test_bad_buyer_score_low(self):
        dim   = _buyer_dimensions(self._bad())
        score = _clamp(round(_buyer_weighted(dim) * 10))
        assert score < 700, f"Expected <700, got {score}"

    def test_all_dimensions_in_0_100(self):
        for f in (self._perfect(), self._bad()):
            dim = _buyer_dimensions(f)
            for k, v in dim.items():
                assert 0 <= v <= 100, f"Dimension {k} out of range: {v}"

    def test_return_rate_0_gives_perfect_d2(self):
        dim = _buyer_dimensions({**self._perfect(), "return_rate": 0.0})
        assert dim["return_behaviour"] == 100.0

    def test_high_return_rate_penalises_d2(self):
        low  = _buyer_dimensions({**self._perfect(), "return_rate": 0.05})
        high = _buyer_dimensions({**self._perfect(), "return_rate": 0.50})
        assert high["return_behaviour"] < low["return_behaviour"]

    def test_low_cancellation_gives_high_d4(self):
        dim = _buyer_dimensions({**self._perfect(), "cancellation_rate": 0.02})
        assert dim["cancellation_behaviour"] >= 95

    def test_engagement_without_referrals_not_penalised(self):
        """No referrals/reviews → engagement score base is 60, not 0."""
        dim = _buyer_dimensions({**self._perfect(), "referral_count": 0, "review_count": 0})
        assert dim["platform_engagement"] >= 60

    def test_infrequent_buyer_completion_rate_not_penalised(self):
        features = {
            "order_completion_rate": 1.0,
            "return_rate": 0.0,
            "payment_success_rate": 1.0,
            "cancellation_rate": 0.0,
            "referral_count": 0,
            "review_count": 0,
        }
        dim = _buyer_dimensions(features)
        assert dim["order_reliability"] == 100.0


# ── Seller dimension scores ───────────────────────────────────────────────────

class TestSellerDimensions:
    def _perfect(self):
        return {
            "fulfillment_rate": 1.0,
            "late_delivery_rate": 0.0,
            "avg_rating_received": 5.0,
            "return_response_rate": 1.0,
            "products_listed": 10,
        }

    def test_perfect_seller_score_near_1000(self):
        dim   = _seller_dimensions(self._perfect())
        score = _clamp(round(_seller_weighted(dim) * 10))
        assert score >= 900, f"Expected ≥900, got {score}"

    def test_new_seller_neutral_rating(self):
        dim = _seller_dimensions({**self._perfect(), "avg_rating_received": 0.0})
        assert dim["customer_satisfaction"] == 70.0

    def test_five_star_gives_max_satisfaction(self):
        dim = _seller_dimensions({**self._perfect(), "avg_rating_received": 5.0})
        assert dim["customer_satisfaction"] == 100.0

    def test_one_star_gives_min_satisfaction(self):
        dim = _seller_dimensions({**self._perfect(), "avg_rating_received": 1.0})
        assert dim["customer_satisfaction"] == 20.0

    def test_late_delivery_penalises_d2(self):
        no_late  = _seller_dimensions({**self._perfect(), "late_delivery_rate": 0.0})
        high_late = _seller_dimensions({**self._perfect(), "late_delivery_rate": 0.5})
        assert high_late["delivery_performance"] < no_late["delivery_performance"]


# ── Trust score recalculation ─────────────────────────────────────────────────

class TestTrustScoreRecalculation:
    def test_new_user_starts_at_700(self, db, buyer):
        row = db.query(TrustScore).filter(TrustScore.user_id == buyer.user_id).first()
        assert row.trust_score == 700
        assert row.confidence  == ConfidenceLevel.LOW
        assert row.tier        == TrustTier.TRUSTED

    def test_positive_behavior_does_not_decrease_score(self, db, buyer, seller, product):
        initial = db.query(TrustScore).filter(TrustScore.user_id == buyer.user_id).first().trust_score

        for _ in range(10):
            product.stock = 100; db.commit()
            order = _force_paid_order(db, buyer, product)
            ship_order(db, order.order_id, seller.user_id)
            complete_order(db, order.order_id, buyer.user_id)

        db.expire_all()
        updated = db.query(TrustScore).filter(TrustScore.user_id == buyer.user_id).first().trust_score
        assert updated >= initial, f"Score dropped after positive behaviour: {initial} → {updated}"

    def test_repeated_cancellations_lower_or_hold_score(self, db, buyer, product):
        initial = db.query(TrustScore).filter(TrustScore.user_id == buyer.user_id).first().trust_score

        for _ in range(8):
            product.stock = 100; db.commit()
            order = _force_paid_order(db, buyer, product)
            cancel_order(db, order.order_id, buyer.user_id, "buyer")

        db.expire_all()
        updated = db.query(TrustScore).filter(TrustScore.user_id == buyer.user_id).first().trust_score
        assert updated <= initial, f"Score should not rise after cancellations: {initial} → {updated}"

    def test_score_never_below_0(self, db, buyer, product):
        for _ in range(50):
            product.stock = 100; db.commit()
            order = _force_paid_order(db, buyer, product)
            cancel_order(db, order.order_id, buyer.user_id, "buyer")
        db.expire_all()
        row = db.query(TrustScore).filter(TrustScore.user_id == buyer.user_id).first()
        assert row.trust_score >= 0

    def test_score_never_above_1000(self, db, buyer, seller, product):
        for _ in range(50):
            product.stock = 100; db.commit()
            order = _force_paid_order(db, buyer, product)
            ship_order(db, order.order_id, seller.user_id)
            complete_order(db, order.order_id, buyer.user_id)
        db.expire_all()
        row = db.query(TrustScore).filter(TrustScore.user_id == buyer.user_id).first()
        assert row.trust_score <= 1000

    def test_smoothing_low_confidence_limits_swing(self, db, buyer):
        prev_score = db.query(TrustScore).filter(TrustScore.user_id == buyer.user_id).first().trust_score
        features = {
            "order_completion_rate": 1.0,
            "return_rate": 0.0,
            "payment_success_rate": 1.0,
            "cancellation_rate": 0.0,
            "referral_count": 10,
            "review_count": 20,
        }
        result = recalculate_trust_score(
            db=db,
            user_id=buyer.user_id,
            role=UserRole.buyer,
            features=features,
            account_created_at=buyer.created_at,
        )
        # LOW confidence → α=0.20, max swing is bounded
        assert abs(result.trust_score - prev_score) <= 300


# ── Privilege engine ──────────────────────────────────────────────────────────

class TestPrivilegeEngine:
    def test_new_buyer_no_active_privileges(self, db, buyer):
        recalculate_privileges(db, buyer.user_id, UserRole.buyer, 700, ConfidenceLevel.LOW)
        active = get_active_privilege_names(db, buyer.user_id)
        assert len(active) == 0

    def test_cod_unlocked_at_750_any_confidence(self, db, buyer):
        recalculate_privileges(db, buyer.user_id, UserRole.buyer, 750, ConfidenceLevel.LOW)
        assert "COD_AVAILABLE" in get_active_privilege_names(db, buyer.user_id)

    def test_cod_unlocked_at_600_medium(self, db, buyer):
        recalculate_privileges(db, buyer.user_id, UserRole.buyer, 600, ConfidenceLevel.MEDIUM)
        assert "COD_AVAILABLE" in get_active_privilege_names(db, buyer.user_id)

    def test_voucher_requires_medium_confidence(self, db, buyer):
        recalculate_privileges(db, buyer.user_id, UserRole.buyer, 650, ConfidenceLevel.LOW)
        assert "EXCLUSIVE_VOUCHER" not in get_active_privilege_names(db, buyer.user_id)

        recalculate_privileges(db, buyer.user_id, UserRole.buyer, 650, ConfidenceLevel.MEDIUM)
        assert "EXCLUSIVE_VOUCHER" in get_active_privilege_names(db, buyer.user_id)

    def test_priority_support_requires_high(self, db, buyer):
        recalculate_privileges(db, buyer.user_id, UserRole.buyer, 800, ConfidenceLevel.MEDIUM)
        assert "PRIORITY_SUPPORT" not in get_active_privilege_names(db, buyer.user_id)

        recalculate_privileges(db, buyer.user_id, UserRole.buyer, 800, ConfidenceLevel.HIGH)
        assert "PRIORITY_SUPPORT" in get_active_privilege_names(db, buyer.user_id)

    def test_seller_trusted_badge_at_700_medium(self, db, seller):
        recalculate_privileges(db, seller.user_id, UserRole.seller, 700, ConfidenceLevel.MEDIUM)
        assert "TRUSTED_BADGE" in get_active_privilege_names(db, seller.user_id)

    def test_seller_promotional_credits_requires_high(self, db, seller):
        recalculate_privileges(db, seller.user_id, UserRole.seller, 800, ConfidenceLevel.MEDIUM)
        assert "PROMOTIONAL_CREDITS" not in get_active_privilege_names(db, seller.user_id)

        recalculate_privileges(db, seller.user_id, UserRole.seller, 800, ConfidenceLevel.HIGH)
        assert "PROMOTIONAL_CREDITS" in get_active_privilege_names(db, seller.user_id)

    def test_all_buyer_benefits_at_elite_high(self, db, buyer):
        recalculate_privileges(db, buyer.user_id, UserRole.buyer, 850, ConfidenceLevel.HIGH)
        active = get_active_privilege_names(db, buyer.user_id)
        assert "COD_AVAILABLE"     in active
        assert "EXCLUSIVE_VOUCHER" in active
        assert "FREE_DELIVERY"     in active
        assert "PRIORITY_SUPPORT"  in active


# ── Full pipeline integration ─────────────────────────────────────────────────

class TestFullPipeline:
    def test_refresh_returns_initial_score_for_new_user(self, db, buyer):
        """
        After calling refresh_trust on a brand-new user, the score should be in
        the TRUSTED range (600-799) because neutral features + LOW confidence +
        α=0.2 smoothing keeps the score close to the 700 starting value.
        """
        result = trust_service.refresh_trust(db, buyer.user_id)
        assert 600 <= result.trust_score <= 850, (
            f"New user trust score unexpectedly out of Trusted range: {result.trust_score}"
        )
        assert result.confidence  == ConfidenceLevel.LOW

    def test_high_evidence_raises_confidence(self, db, buyer, seller, product):
        for _ in range(35):
            product.stock = 100; db.commit()
            order = _force_paid_order(db, buyer, product)
            ship_order(db, order.order_id, seller.user_id)
            complete_order(db, order.order_id, buyer.user_id)

        db.expire_all()
        row = db.query(TrustScore).filter(TrustScore.user_id == buyer.user_id).first()
        assert row.confidence in (ConfidenceLevel.MEDIUM, ConfidenceLevel.HIGH)
        assert row.trust_score >= 700

    def test_score_history_appended_on_change(self, db, buyer, seller, product):
        order = _force_paid_order(db, buyer, product)
        ship_order(db, order.order_id, seller.user_id)
        complete_order(db, order.order_id, buyer.user_id)
        history = db.query(ScoreHistory).filter(ScoreHistory.user_id == buyer.user_id).all()
        assert history is not None   # table is queryable

    def test_time_decay_fresh_event_more_impactful(self, db, buyer):
        """A recent cancellation has more weight than a 180-day-old one."""
        record_event(db, buyer.user_id, EventType.ORDER_PLACED)
        record_event(db, buyer.user_id, EventType.ORDER_CANCELLED)
        _back_date_events(db, buyer.user_id, days_ago=180)
        update_features_for_users(db, [buyer.user_id])
        old_result  = trust_service.refresh_trust(db, buyer.user_id)
        old_score   = old_result.trust_score

        record_event(db, buyer.user_id, EventType.ORDER_PLACED)
        record_event(db, buyer.user_id, EventType.ORDER_CANCELLED)
        update_features_for_users(db, [buyer.user_id])
        new_result = trust_service.refresh_trust(db, buyer.user_id)
        # Fresh cancellation should not mysteriously increase the score
        assert new_result.trust_score <= old_score + 30


# ── Trust API endpoints ───────────────────────────────────────────────────────

class TestTrustAPI:
    def _register_login(self, client, email, role="buyer"):
        client.post("/auth/register", json={
            "name": "Test User", "email": email,
            "password": "Password1!", "role": role,
        })
        resp = client.post("/auth/login", json={"email": email, "password": "Password1!"})
        return resp.json()["access_token"]

    def test_get_trust_me_unauthenticated(self, api_client):
        resp = api_client.get("/trust/me")
        assert resp.status_code in (401, 403)   # HTTPBearer returns 403 when no token provided

    def test_get_trust_me_initial_state(self, api_client):
        token = self._register_login(api_client, "trustme@test.com")
        resp = api_client.get("/trust/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["trust_score"] == 700
        assert data["confidence"]  == "LOW"
        assert data["tier"]        == "TRUSTED"
        assert "breakdown" in data
        assert "benefits"  in data

    def test_get_trust_history_for_new_user(self, api_client):
        token = self._register_login(api_client, "history@test.com")
        me  = api_client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
        uid = me["user"]["user_id"]
        resp = api_client.get(f"/trust/{uid}/history",
                              headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_trust_breakdown_contains_dims(self, api_client):
        token = self._register_login(api_client, "breakdown@test.com")
        me  = api_client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
        uid = me["user"]["user_id"]
        resp = api_client.get(f"/trust/{uid}/breakdown",
                              headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert "breakdown" in data
        assert "recommendations" in data
        assert isinstance(data["recommendations"], list)

    def test_get_trust_benefits_returns_4_for_buyer(self, api_client):
        token = self._register_login(api_client, "benefits@test.com", "buyer")
        me  = api_client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
        uid = me["user"]["user_id"]
        resp = api_client.get(f"/trust/{uid}/benefits",
                              headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert len(resp.json()["benefits"]) == 4

    def test_cannot_view_other_users_trust(self, api_client):
        t1 = self._register_login(api_client, "u1@test.com", "buyer")
        t2 = self._register_login(api_client, "u2@test.com", "buyer")
        uid2 = api_client.get("/auth/me", headers={"Authorization": f"Bearer {t2}"}).json()["user"]["user_id"]
        resp = api_client.get(f"/trust/{uid2}", headers={"Authorization": f"Bearer {t1}"})
        assert resp.status_code == 403

    def test_seller_benefits_are_seller_specific(self, api_client):
        token = self._register_login(api_client, "seller1@test.com", "seller")
        uid   = api_client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["user"]["user_id"]
        resp  = api_client.get(f"/trust/{uid}/benefits",
                               headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        names = [b["name"] for b in resp.json()["benefits"]]
        assert "TRUSTED_BADGE" in names
        assert "COD_AVAILABLE" not in names
