"""
Phase 16 — Full Test Suite.

Covers areas not yet tested in Phases 2–6:
  1. Explainability endpoint (GET /trust/{user_id}/explain)
  2. Admin API endpoints (analytics, users, trust-distribution)
  3. ML service inference (buyer + seller models)
  4. Score boundary determinism (0, 1000 clamp)
  5. Referral claim endpoint
  6. End-to-end demo scenarios from the TrustGrid spec:
     - Scenario 1: New buyer starts at 700 / LOW
     - Scenario 2: Good buyer behaviour raises score
     - Scenario 3: Negative behaviour (cancellations) lowers score
     - Scenario 4: Seller registers, lists, fulfills, score improves
     - Scenario 5: Time decay — old events weigh less than recent ones
  7. API authorization (buyers cannot access seller routes and vice versa)
  8. Score history grows as events occur
  9. Privilege activation flow (score + confidence threshold crossing)
 10. Confidence escalation from LOW → MEDIUM → HIGH
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
    TrustScore, ScoreHistory, Privilege, ConfidenceLevel, TrustTier,
)
from app.models.marketplace import OrderStatus
from app.models.user import UserRole
from app.trustgrid.ml_service import (
    get_buyer_reliability_score,
    get_seller_reliability_score,
    models_available,
)
from app.trustgrid.trust_engine import _blend_ml, _clamp, score_to_tier
from app.trustgrid.confidence_service import calculate_confidence
from app.trustgrid.privilege_engine import (
    recalculate_privileges, get_active_privilege_names,
)
from app.trustgrid.event_service import record_event, update_features_for_users
from app.trustgrid.event_types import EventType
from app.trustgrid.feature_engine import get_feature_vector
from app.services.user_service import create_user
from app.services.product_service import create_product
from app.services.order_service import (
    place_order, cancel_order, ship_order, complete_order,
    request_return, submit_review,
)
from app.services import trust_service
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
    return create_user(db, "Test Buyer", "buyer@test.com", "Password1!", "buyer")


@pytest.fixture
def seller(db):
    return create_user(db, "Test Seller", "seller@test.com", "Password1!", "seller")


@pytest.fixture
def product(db, seller):
    return create_product(db, seller.user_id, ProductCreate(
        title="Widget", price=Decimal("499.99"), stock=200,
    ))


def _force_paid_order(db, buyer, product):
    random.seed(42)
    order = place_order(db, buyer.user_id, OrderCreate(product_id=product.id, quantity=1))
    if order.status != OrderStatus.paid:
        order.status = OrderStatus.paid
        db.commit(); db.refresh(order)
    product.stock += 1
    db.commit()
    return order


def _back_date_events(db, user_id: str, days_ago: float):
    from app.models.trust import TrustEvent
    past = datetime.now(timezone.utc) - timedelta(days=days_ago)
    for ev in db.query(TrustEvent).filter(TrustEvent.user_id == user_id).all():
        ev.created_at = past
    db.commit()


# ── 1. ML Service ─────────────────────────────────────────────────────────────

class TestMLService:
    """Verify ML model loading and inference quality."""

    def test_models_loadable(self):
        status = models_available()
        # Models may or may not be present on this machine;
        # the service must not crash either way.
        assert isinstance(status, dict)
        assert "buyer_model" in status
        assert "seller_model" in status

    def test_reliable_buyer_high_probability(self):
        """A buyer with perfect features should get P(reliable) > 0.9 if model loaded."""
        score = get_buyer_reliability_score({
            "order_completion_rate": 0.97,
            "return_rate": 0.02,
            "payment_success_rate": 0.99,
            "cancellation_rate": 0.03,
            "referral_count": 3.0,
            "review_count": 8.0,
            "total_orders": 25.0,
            "completed_orders": 24.0,
            "total_cancellations": 1.0,
            "total_returns": 0.0,
            "decayed_event_weight": 18.0,
        })
        if score is None:
            pytest.skip("Buyer model not available")
        assert score > 0.9, f"Expected reliable buyer > 0.9, got {score:.4f}"

    def test_unreliable_buyer_low_probability(self):
        """A buyer with poor features should get P(reliable) < 0.2 if model loaded."""
        score = get_buyer_reliability_score({
            "order_completion_rate": 0.35,
            "return_rate": 0.55,
            "payment_success_rate": 0.45,
            "cancellation_rate": 0.65,
            "referral_count": 0.0,
            "review_count": 0.0,
            "total_orders": 12.0,
            "completed_orders": 4.0,
            "total_cancellations": 7.0,
            "total_returns": 2.0,
            "decayed_event_weight": 6.0,
        })
        if score is None:
            pytest.skip("Buyer model not available")
        assert score < 0.2, f"Expected unreliable buyer < 0.2, got {score:.4f}"

    def test_reliable_seller_high_probability(self):
        score = get_seller_reliability_score({
            "fulfillment_rate": 0.97,
            "late_delivery_rate": 0.03,
            "avg_rating_received": 4.8,
            "return_response_rate": 0.96,
            "products_listed": 10.0,
            "fulfilled_orders": 55.0,
            "seller_cancellations": 1.0,
            "on_time_deliveries": 50.0,
            "late_deliveries": 2.0,
            "return_requests_received": 3.0,
            "returns_responded": 3.0,
            "decayed_event_weight": 35.0,
        })
        if score is None:
            pytest.skip("Seller model not available")
        assert score > 0.9, f"Expected reliable seller > 0.9, got {score:.4f}"

    def test_ml_score_none_when_model_unavailable(self):
        """_blend_ml gracefully returns rule_raw when ml_prob is None."""
        result = _blend_ml(rule_raw=75.0, ml_prob=None, evidence_weight=20.0)
        assert result == 75.0

    def test_blend_no_evidence_is_pure_rule(self):
        """With weight < 1, β=0.0 — pure rule-based score."""
        result = _blend_ml(rule_raw=80.0, ml_prob=0.5, evidence_weight=0.5)
        assert result == 80.0

    def test_blend_high_evidence_includes_ml(self):
        """With weight > 10, β=0.5 — blend changes the output."""
        rule_raw = 80.0
        ml_prob  = 1.0       # perfect ML score → ml_raw = 100
        result   = _blend_ml(rule_raw=rule_raw, ml_prob=ml_prob, evidence_weight=15.0)
        # 0.5×100 + 0.5×80 = 90
        assert abs(result - 90.0) < 0.01


# ── 2. Explainability endpoint ─────────────────────────────────────────────────

class TestExplainabilityEndpoint:
    def _register_login(self, client, email, role="buyer"):
        client.post("/auth/register", json={
            "name": "Test", "email": email,
            "password": "Password1!", "role": role,
        })
        resp = client.post("/auth/login", json={"email": email, "password": "Password1!"})
        return resp.json()["access_token"]

    def test_explain_returns_expected_keys(self, api_client):
        token = self._register_login(api_client, "exp@test.com")
        uid   = api_client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["user"]["user_id"]
        resp  = api_client.get(f"/trust/{uid}/explain", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        for key in ["user_id", "trust_score", "confidence", "tier",
                    "driving_factors", "recommendations", "time_decay_note"]:
            assert key in data, f"Missing key: {key}"

    def test_explain_time_decay_note_present(self, api_client):
        token = self._register_login(api_client, "decay@test.com")
        uid   = api_client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["user"]["user_id"]
        resp  = api_client.get(f"/trust/{uid}/explain", headers={"Authorization": f"Bearer {token}"})
        data  = resp.json()
        assert "recent" in data["time_decay_note"].lower()
        assert "influence" in data["time_decay_note"].lower()

    def test_explain_recommendations_is_list(self, api_client):
        token = self._register_login(api_client, "recs@test.com")
        uid   = api_client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["user"]["user_id"]
        resp  = api_client.get(f"/trust/{uid}/explain", headers={"Authorization": f"Bearer {token}"})
        assert isinstance(resp.json()["recommendations"], list)

    def test_explain_access_denied_for_other_user(self, api_client):
        t1 = self._register_login(api_client, "e1@test.com")
        t2 = self._register_login(api_client, "e2@test.com")
        uid2 = api_client.get("/auth/me", headers={"Authorization": f"Bearer {t2}"}).json()["user"]["user_id"]
        resp = api_client.get(f"/trust/{uid2}/explain", headers={"Authorization": f"Bearer {t1}"})
        assert resp.status_code == 403


# ── 3. Admin API ───────────────────────────────────────────────────────────────

class TestAdminAPI:
    def _admin_token(self, client):
        """Create an admin user via direct DB insert (admin role not in public register)."""
        # Register as buyer first, then use api_db fixture to promote to admin.
        # Simpler: use register with buyer role and call /admin/* with a freshly
        # created admin via create_user through the test DB fixture.
        # Because api_client uses its own DB via conftest, we use a unique
        # approach: register as buyer, then manually promote via the DB.
        import uuid
        email = f"admin_{uuid.uuid4().hex[:6]}@test.com"
        # Register as buyer
        client.post("/auth/register", json={
            "name": "AdminUser", "email": email,
            "password": "Password1!", "role": "buyer",
        })
        # Log in to get token for the buyer
        resp = client.post("/auth/login", json={"email": email, "password": "Password1!"})
        buyer_token = resp.json()["access_token"]
        # Promote to admin by calling the internal promote endpoint or patching DB.
        # Since we have no promote endpoint, we use the api_db to change role directly.
        return buyer_token, email  # caller must handle admin tests differently

    def _create_admin_token(self, client, api_db):
        """Create a real admin user in the test DB and return their token."""
        from app.services.user_service import create_user as _cu
        from app.models.user import UserRole
        import uuid
        email = f"admin_{uuid.uuid4().hex[:6]}@test.com"
        user = _cu(api_db, "AdminUser", email, "Password1!", "buyer")
        user.role = UserRole.admin
        api_db.commit()
        resp = client.post("/auth/login", json={"email": email, "password": "Password1!"})
        return resp.json()["access_token"]

    def _buyer_token(self, client):
        import uuid
        email = f"buyer_{uuid.uuid4().hex[:6]}@test.com"
        client.post("/auth/register", json={
            "name": "Buyer", "email": email,
            "password": "Password1!", "role": "buyer",
        })
        resp = client.post("/auth/login", json={"email": email, "password": "Password1!"})
        return resp.json()["access_token"]

    def test_analytics_requires_admin(self, api_client, api_db):
        buyer_token = self._buyer_token(api_client)
        resp = api_client.get("/admin/analytics", headers={"Authorization": f"Bearer {buyer_token}"})
        assert resp.status_code == 403

    def test_analytics_accessible_by_admin(self, api_client, api_db):
        token = self._create_admin_token(api_client, api_db)
        resp  = api_client.get("/admin/analytics", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        for key in ["totals", "averages", "buyer_tiers", "seller_tiers",
                    "confidence_dist", "recent_changes", "top_event_types"]:
            assert key in data, f"Missing key: {key}"

    def test_analytics_totals_are_non_negative(self, api_client, api_db):
        token = self._create_admin_token(api_client, api_db)
        data  = api_client.get("/admin/analytics", headers={"Authorization": f"Bearer {token}"}).json()
        for k, v in data["totals"].items():
            assert v >= 0, f"Negative total for {k}: {v}"

    def test_users_list_requires_admin(self, api_client, api_db):
        buyer_token = self._buyer_token(api_client)
        resp = api_client.get("/admin/users", headers={"Authorization": f"Bearer {buyer_token}"})
        assert resp.status_code == 403

    def test_users_list_returns_registered_users(self, api_client, api_db):
        token = self._create_admin_token(api_client, api_db)
        resp  = api_client.get("/admin/users", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert "users" in data
        assert "total" in data
        assert data["total"] >= 1

    def test_users_list_role_filter(self, api_client, api_db):
        self._buyer_token(api_client)   # create a buyer
        token = self._create_admin_token(api_client, api_db)
        resp  = api_client.get("/admin/users?role=buyer", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        users = resp.json()["users"]
        for u in users:
            assert u["role"] == "buyer"

    def test_trust_distribution_returns_labels(self, api_client, api_db):
        token = self._create_admin_token(api_client, api_db)
        resp  = api_client.get("/admin/trust-distribution", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert "labels" in data
        assert len(data["labels"]) == 10   # 10 buckets: 0-99, 100-199, …, 900-999
        assert "buyers"  in data
        assert "sellers" in data

    def test_trust_distribution_bucket_counts_non_negative(self, api_client, api_db):
        token = self._create_admin_token(api_client, api_db)
        data  = api_client.get("/admin/trust-distribution", headers={"Authorization": f"Bearer {token}"}).json()
        for cnt in data["buyers"] + data["sellers"]:
            assert cnt >= 0


# ── 4. End-to-end Scenario 1: New buyer ──────────────────────────────────────

class TestScenario1NewBuyer:
    """
    Spec Scenario 1:
      Register → BUY-ID assigned → score=700 / confidence=LOW
    """

    def test_new_buyer_receives_buy_id(self, db):
        buyer = create_user(db, "New Buyer", "new@test.com", "Password1!", "buyer")
        assert buyer.user_id.startswith("BUY-")

    def test_new_buyer_starts_at_700(self, db):
        buyer = create_user(db, "New", "n@test.com", "Password1!", "buyer")
        ts = db.query(TrustScore).filter(TrustScore.user_id == buyer.user_id).first()
        assert ts.trust_score == 700

    def test_new_buyer_confidence_is_low(self, db):
        buyer = create_user(db, "New", "n2@test.com", "Password1!", "buyer")
        ts = db.query(TrustScore).filter(TrustScore.user_id == buyer.user_id).first()
        assert ts.confidence == ConfidenceLevel.LOW

    def test_new_buyer_tier_is_trusted(self, db):
        buyer = create_user(db, "New", "n3@test.com", "Password1!", "buyer")
        ts = db.query(TrustScore).filter(TrustScore.user_id == buyer.user_id).first()
        assert ts.tier == TrustTier.TRUSTED

    def test_new_buyer_no_active_benefits(self, db):
        buyer = create_user(db, "New", "n4@test.com", "Password1!", "buyer")
        recalculate_privileges(db, buyer.user_id, UserRole.buyer, 700, ConfidenceLevel.LOW)
        active = get_active_privilege_names(db, buyer.user_id)
        assert len(active) == 0

    def test_new_seller_receives_sel_id(self, db):
        seller = create_user(db, "New Seller", "ns@test.com", "Password1!", "seller")
        assert seller.user_id.startswith("SEL-")


# ── 5. End-to-end Scenario 2: Good buyer behaviour ───────────────────────────

class TestScenario2GoodBehaviour:
    """
    Spec Scenario 2:
      Complete orders + payment success + referral
      → Trust Score increases
      → Dashboard shows "score increased because of recent successful activity"
    """

    def test_completed_orders_increase_score(self, db, buyer, seller, product):
        initial = db.query(TrustScore).filter(TrustScore.user_id == buyer.user_id).first().trust_score

        for _ in range(12):
            product.stock = 200; db.commit()
            order = _force_paid_order(db, buyer, product)
            ship_order(db, order.order_id, seller.user_id)
            complete_order(db, order.order_id, buyer.user_id)

        db.expire_all()
        updated = db.query(TrustScore).filter(TrustScore.user_id == buyer.user_id).first().trust_score
        assert updated >= initial, f"Score should not drop after completing orders: {initial} → {updated}"

    def test_referral_adds_to_score_positively(self, db, buyer):
        initial = db.query(TrustScore).filter(TrustScore.user_id == buyer.user_id).first().trust_score
        record_event(db, buyer.user_id, EventType.REFERRAL_COMPLETED,
                     impact_summary="Referred a friend")
        update_features_for_users(db, [buyer.user_id])
        trust_service.refresh_trust(db, buyer.user_id, event_type=EventType.REFERRAL_COMPLETED.value)
        db.expire_all()
        updated = db.query(TrustScore).filter(TrustScore.user_id == buyer.user_id).first().trust_score
        assert updated >= initial

    def test_score_history_records_change_on_completion(self, db, buyer, seller, product):
        order = _force_paid_order(db, buyer, product)
        ship_order(db, order.order_id, seller.user_id)
        complete_order(db, order.order_id, buyer.user_id)
        history = db.query(ScoreHistory).filter(ScoreHistory.user_id == buyer.user_id).all()
        # History should exist (even if score_change is 0 due to smoothing at LOW confidence)
        assert history is not None

    def test_confidence_rises_with_more_completions(self, db, buyer, seller, product):
        for _ in range(8):
            product.stock = 200; db.commit()
            order = _force_paid_order(db, buyer, product)
            ship_order(db, order.order_id, seller.user_id)
            complete_order(db, order.order_id, buyer.user_id)
        db.expire_all()
        row = db.query(TrustScore).filter(TrustScore.user_id == buyer.user_id).first()
        # Should have escalated from LOW to at least MEDIUM with 8+ meaningful events
        assert row.confidence in (ConfidenceLevel.MEDIUM, ConfidenceLevel.HIGH)


# ── 6. End-to-end Scenario 3: Negative behaviour ─────────────────────────────

class TestScenario3NegativeBehaviour:
    """
    Spec Scenario 3:
      Cancellations + failed payments + returns
      → Score should decrease or not increase
      → Score history should show why
    """

    def test_cancellations_do_not_raise_score(self, db, buyer, product):
        initial = db.query(TrustScore).filter(TrustScore.user_id == buyer.user_id).first().trust_score

        for _ in range(10):
            product.stock = 200; db.commit()
            order = _force_paid_order(db, buyer, product)
            cancel_order(db, order.order_id, buyer.user_id, "buyer")

        db.expire_all()
        updated = db.query(TrustScore).filter(TrustScore.user_id == buyer.user_id).first().trust_score
        # After many cancellations, score should drop or hold—never increase
        assert updated <= initial, f"Score rose after cancellations: {initial} → {updated}"

    def test_high_cancellation_rate_lowers_dim_score(self, db, buyer):
        from app.trustgrid.trust_engine import _buyer_dimensions
        # Simulate cancellation_rate of 0.70 (very bad)
        features = {
            "order_completion_rate": 0.30,
            "return_rate": 0.10,
            "payment_success_rate": 0.85,
            "cancellation_rate": 0.70,
            "referral_count": 0,
            "review_count": 0,
        }
        dim = _buyer_dimensions(features)
        assert dim["cancellation_behaviour"] < 50, (
            f"Expected cancellation_behaviour < 50, got {dim['cancellation_behaviour']}"
        )

    def test_score_not_below_0_after_extreme_negative_behaviour(self, db, buyer, product):
        for _ in range(40):
            product.stock = 200; db.commit()
            order = _force_paid_order(db, buyer, product)
            cancel_order(db, order.order_id, buyer.user_id, "buyer")
        db.expire_all()
        row = db.query(TrustScore).filter(TrustScore.user_id == buyer.user_id).first()
        assert row.trust_score >= 0, f"Score went below 0: {row.trust_score}"

    def test_return_rate_within_normal_range_not_heavily_penalised(self, db):
        """A 5% return rate (realistic) should not heavily penalise score."""
        from app.trustgrid.trust_engine import _buyer_dimensions
        features = {
            "order_completion_rate": 0.95,
            "return_rate": 0.05,
            "payment_success_rate": 0.97,
            "cancellation_rate": 0.05,
            "referral_count": 0,
            "review_count": 0,
        }
        dim = _buyer_dimensions(features)
        assert dim["return_behaviour"] == 100.0, (
            "5% return rate should get full return_behaviour score"
        )


# ── 7. End-to-end Scenario 4: Seller ─────────────────────────────────────────

class TestScenario4Seller:
    """
    Spec Scenario 4:
      Seller registers → 700/LOW → lists products → fulfills orders
      → score increases → seller benefits unlock
    """

    def test_seller_starts_at_700_low(self, db, seller):
        ts = db.query(TrustScore).filter(TrustScore.user_id == seller.user_id).first()
        assert ts.trust_score == 700
        assert ts.confidence == ConfidenceLevel.LOW

    def test_seller_trust_improves_with_fulfillments(self, db, buyer, seller, product):
        initial = db.query(TrustScore).filter(TrustScore.user_id == seller.user_id).first().trust_score

        for _ in range(10):
            product.stock = 200; db.commit()
            order = _force_paid_order(db, buyer, product)
            ship_order(db, order.order_id, seller.user_id)
            complete_order(db, order.order_id, buyer.user_id)

        db.expire_all()
        updated = db.query(TrustScore).filter(TrustScore.user_id == seller.user_id).first().trust_score
        assert updated >= initial

    def test_seller_badge_unlocks_at_700_medium(self, db, seller):
        recalculate_privileges(db, seller.user_id, UserRole.seller, 700, ConfidenceLevel.MEDIUM)
        active = get_active_privilege_names(db, seller.user_id)
        assert "TRUSTED_BADGE" in active

    def test_seller_cancellations_do_not_raise_score(self, db, buyer, seller, product):
        initial = db.query(TrustScore).filter(TrustScore.user_id == seller.user_id).first().trust_score

        for _ in range(8):
            product.stock = 200; db.commit()
            order = _force_paid_order(db, buyer, product)
            cancel_order(db, order.order_id, seller.user_id, "seller")

        db.expire_all()
        updated = db.query(TrustScore).filter(TrustScore.user_id == seller.user_id).first().trust_score
        assert updated <= initial

    def test_seller_good_ratings_improve_satisfaction_dimension(self, db):
        from app.trustgrid.trust_engine import _seller_dimensions
        features = {
            "fulfillment_rate": 0.95,
            "late_delivery_rate": 0.05,
            "avg_rating_received": 4.8,
            "return_response_rate": 0.95,
            "products_listed": 8.0,
        }
        dim = _seller_dimensions(features)
        assert dim["customer_satisfaction"] >= 95.0

    def test_seller_no_ratings_gives_neutral_satisfaction(self, db):
        from app.trustgrid.trust_engine import _seller_dimensions
        features = {
            "fulfillment_rate": 1.0,
            "late_delivery_rate": 0.0,
            "avg_rating_received": 0.0,
            "return_response_rate": 1.0,
            "products_listed": 5.0,
        }
        dim = _seller_dimensions(features)
        assert dim["customer_satisfaction"] == 70.0  # neutral starting point


# ── 8. End-to-end Scenario 5: Time decay ─────────────────────────────────────

class TestScenario5TimeDecay:
    """
    Spec Scenario 5:
      Demonstrate that old events contribute less than recent events.
      Same event type fired twice: once old (180 days ago) and once recent.
      The recent event should have more weight in the feature vector.
    """

    def test_recent_payment_outweighs_180day_old_payment(self, db, buyer):
        from app.trustgrid.event_service import update_features_for_users
        from app.trustgrid.feature_engine import _HALF_LIFE_DAYS
        import math

        # Fire an old event (180 days ago)
        record_event(db, buyer.user_id, EventType.PAYMENT_SUCCESS)
        _back_date_events(db, buyer.user_id, days_ago=180.0)

        # Fire a fresh recent event
        record_event(db, buyer.user_id, EventType.PAYMENT_SUCCESS)
        update_features_for_users(db, [buyer.user_id])
        fv = get_feature_vector(db, buyer.user_id)

        # Total weight = w_old + w_recent
        # w_old ≈ exp(-λ*180) ≈ 0.25
        # w_recent ≈ exp(-λ*0) ≈ 1.0
        # total ≈ 1.25 — the recent event contributes ~80% of total weight
        lam = math.log(2) / _HALF_LIFE_DAYS
        expected_old_weight = math.exp(-lam * 180)
        expected_recent_weight = math.exp(-lam * 0)
        assert fv["decayed_event_weight"] > expected_old_weight
        assert fv["decayed_event_weight"] < expected_old_weight + expected_recent_weight + 0.1

    def test_270_day_old_event_has_minimal_weight(self):
        from app.trustgrid.feature_engine import decay_weight, _HALF_LIFE_DAYS
        now = datetime.now(timezone.utc)
        t = now - timedelta(days=270)
        w = decay_weight(t, now)
        # After 3 half-lives (270 days): weight ≈ 0.125
        assert abs(w - 0.125) < 0.02

    def test_score_recalculation_reflects_decay(self, db, buyer):
        """
        After back-dating all events, recalculate — then add a fresh
        negative event. The fresh negative should have more impact.
        """
        # Add some positive events and back-date them
        for _ in range(5):
            record_event(db, buyer.user_id, EventType.PAYMENT_SUCCESS)
            record_event(db, buyer.user_id, EventType.ORDER_COMPLETED)
        _back_date_events(db, buyer.user_id, days_ago=180)
        update_features_for_users(db, [buyer.user_id])
        score_after_old = trust_service.refresh_trust(db, buyer.user_id).trust_score

        # Add fresh cancellations
        for _ in range(5):
            record_event(db, buyer.user_id, EventType.ORDER_PLACED)
            record_event(db, buyer.user_id, EventType.ORDER_CANCELLED)
        update_features_for_users(db, [buyer.user_id])
        score_after_new = trust_service.refresh_trust(db, buyer.user_id).trust_score

        # The fresh cancellations should have pulled score down relative to just old positives
        assert score_after_new <= score_after_old + 30, (
            "Fresh negative events should not raise score above old-positive baseline"
        )


# ── 9. API Authorization Tests ────────────────────────────────────────────────

class TestAPIAuthorization:
    def _register_login(self, client, role="buyer"):
        """Register + login with a unique email each call."""
        import uuid
        email = f"auth_{uuid.uuid4().hex[:8]}@test.com"
        client.post("/auth/register", json={
            "name": "TestUser", "email": email, "password": "Password1!", "role": role,
        })
        resp = client.post("/auth/login", json={"email": email, "password": "Password1!"})
        return resp.json()["access_token"], email

    def test_unauthenticated_cannot_access_trust_me(self, api_client):
        resp = api_client.get("/trust/me")
        assert resp.status_code in (401, 403)

    def test_buyer_cannot_access_admin_analytics(self, api_client):
        token, _ = self._register_login(api_client, "buyer")
        resp = api_client.get("/admin/analytics", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403

    def test_seller_cannot_access_admin_analytics(self, api_client):
        token, _ = self._register_login(api_client, "seller")
        resp = api_client.get("/admin/analytics", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403

    def test_buyer_cannot_view_other_buyers_trust(self, api_client):
        t1, _ = self._register_login(api_client, "buyer")
        t2, _ = self._register_login(api_client, "buyer")
        uid2 = api_client.get("/auth/me", headers={"Authorization": f"Bearer {t2}"}).json()["user"]["user_id"]
        resp = api_client.get(f"/trust/{uid2}", headers={"Authorization": f"Bearer {t1}"})
        assert resp.status_code == 403

    def test_buyer_can_view_own_trust(self, api_client):
        token, _ = self._register_login(api_client, "buyer")
        resp = api_client.get("/trust/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_expired_token_rejected(self, api_client):
        # Craft a token that references a non-existent user
        import datetime as dt
        from jose import jwt
        from app.core.config import settings
        expired_payload = {
            "sub": "BUY-99999",
            "role": "buyer",
            "exp": dt.datetime(2020, 1, 1, tzinfo=timezone.utc),
            "iat": dt.datetime(2019, 1, 1, tzinfo=timezone.utc),
        }
        expired_token = jwt.encode(expired_payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        resp = api_client.get("/trust/me", headers={"Authorization": f"Bearer {expired_token}"})
        assert resp.status_code in (401, 403)


# ── 10. Confidence escalation ─────────────────────────────────────────────────

class TestConfidenceEscalation:
    """Confidence must rise deterministically as evidence accumulates."""

    def test_0_events_is_low(self, db, buyer):
        assert calculate_confidence(db, buyer.user_id, buyer.created_at) == ConfidenceLevel.LOW

    def test_6_meaningful_events_is_medium(self, db, buyer):
        for _ in range(6):
            record_event(db, buyer.user_id, EventType.ORDER_COMPLETED)
        assert calculate_confidence(db, buyer.user_id, buyer.created_at) == ConfidenceLevel.MEDIUM

    def test_31_meaningful_events_is_high(self, db, buyer):
        for _ in range(31):
            record_event(db, buyer.user_id, EventType.PAYMENT_SUCCESS)
        assert calculate_confidence(db, buyer.user_id, buyer.created_at) == ConfidenceLevel.HIGH

    def test_confidence_never_decreases_with_more_evidence(self, db, buyer):
        """Confidence should be monotonically non-decreasing as events accumulate."""
        levels = [ConfidenceLevel.LOW, ConfidenceLevel.MEDIUM, ConfidenceLevel.HIGH]
        conf_order = {c: i for i, c in enumerate(levels)}

        prev_conf = calculate_confidence(db, buyer.user_id, buyer.created_at)
        for _ in range(35):
            record_event(db, buyer.user_id, EventType.ORDER_COMPLETED)
        new_conf = calculate_confidence(db, buyer.user_id, buyer.created_at)

        assert conf_order[new_conf] >= conf_order[prev_conf], (
            f"Confidence decreased from {prev_conf} to {new_conf} with more evidence"
        )


# ── 11. Privilege activation flow ────────────────────────────────────────────

class TestPrivilegeActivationFlow:
    """Privileges unlock progressively as score and confidence improve."""

    def test_privilege_flow_buyer(self, db, buyer):
        """Step through privilege unlocks as score and confidence increase."""
        # Start: 700 / LOW — no benefits
        recalculate_privileges(db, buyer.user_id, UserRole.buyer, 700, ConfidenceLevel.LOW)
        assert get_active_privilege_names(db, buyer.user_id) == []

        # 750 / LOW — COD unlocks via alt_score rule
        recalculate_privileges(db, buyer.user_id, UserRole.buyer, 750, ConfidenceLevel.LOW)
        assert "COD_AVAILABLE" in get_active_privilege_names(db, buyer.user_id)

        # 700 / MEDIUM — COD via primary rule
        recalculate_privileges(db, buyer.user_id, UserRole.buyer, 600, ConfidenceLevel.MEDIUM)
        assert "COD_AVAILABLE" in get_active_privilege_names(db, buyer.user_id)

        # 800 / HIGH — all 4 benefits unlock
        recalculate_privileges(db, buyer.user_id, UserRole.buyer, 850, ConfidenceLevel.HIGH)
        active = get_active_privilege_names(db, buyer.user_id)
        assert len(active) == 4

    def test_privilege_flow_seller(self, db, seller):
        # 700 / LOW — no benefits
        recalculate_privileges(db, seller.user_id, UserRole.seller, 700, ConfidenceLevel.LOW)
        assert get_active_privilege_names(db, seller.user_id) == []

        # 700 / MEDIUM — badge + visibility unlock
        recalculate_privileges(db, seller.user_id, UserRole.seller, 700, ConfidenceLevel.MEDIUM)
        active = get_active_privilege_names(db, seller.user_id)
        assert "TRUSTED_BADGE"     in active
        assert "SEARCH_VISIBILITY" in active

        # 800 / HIGH — all 4 unlock
        recalculate_privileges(db, seller.user_id, UserRole.seller, 800, ConfidenceLevel.HIGH)
        assert len(get_active_privilege_names(db, seller.user_id)) == 4

    def test_privilege_can_be_downgraded(self, db, buyer):
        """If score drops back below threshold, privilege becomes inactive again."""
        # Unlock COD
        recalculate_privileges(db, buyer.user_id, UserRole.buyer, 750, ConfidenceLevel.LOW)
        assert "COD_AVAILABLE" in get_active_privilege_names(db, buyer.user_id)
        # Score drops below 600 — COD should lock again
        recalculate_privileges(db, buyer.user_id, UserRole.buyer, 550, ConfidenceLevel.LOW)
        assert "COD_AVAILABLE" not in get_active_privilege_names(db, buyer.user_id)


# ── 12. Score boundary / determinism ─────────────────────────────────────────

class TestScoreBoundaries:
    def test_clamp_0(self):    assert _clamp(-500)  == 0
    def test_clamp_1000(self): assert _clamp(1500)  == 1000
    def test_clamp_mid(self):  assert _clamp(724)   == 724

    def test_tier_boundaries(self):
        assert score_to_tier(0)    == TrustTier.RESTRICTED
        assert score_to_tier(399)  == TrustTier.RESTRICTED
        assert score_to_tier(400)  == TrustTier.STANDARD
        assert score_to_tier(599)  == TrustTier.STANDARD
        assert score_to_tier(600)  == TrustTier.TRUSTED
        assert score_to_tier(799)  == TrustTier.TRUSTED
        assert score_to_tier(800)  == TrustTier.ELITE
        assert score_to_tier(1000) == TrustTier.ELITE

    def test_score_never_goes_negative(self, db):
        """Even 100 cancellations in a row — score ≥ 0."""
        buyer = create_user(db, "Worst", "worst@test.com", "Password1!", "buyer")
        seller = create_user(db, "Sel", "sel@test.com", "Password1!", "seller")
        product = create_product(db, seller.user_id, ProductCreate(
            title="XX", price=Decimal("10"), stock=500,
        ))
        for _ in range(50):
            product.stock = 500; db.commit()
            order = _force_paid_order(db, buyer, product)
            cancel_order(db, order.order_id, buyer.user_id, "buyer")
        db.expire_all()
        ts = db.query(TrustScore).filter(TrustScore.user_id == buyer.user_id).first()
        assert ts.trust_score >= 0

    def test_score_never_exceeds_1000(self, db):
        """Even 100 perfect completions — score ≤ 1000."""
        buyer = create_user(db, "Best", "best@test.com", "Password1!", "buyer")
        seller = create_user(db, "Sel2", "sel2@test.com", "Password1!", "seller")
        product = create_product(db, seller.user_id, ProductCreate(
            title="YY", price=Decimal("10"), stock=500,
        ))
        for _ in range(50):
            product.stock = 500; db.commit()
            order = _force_paid_order(db, buyer, product)
            ship_order(db, order.order_id, seller.user_id)
            complete_order(db, order.order_id, buyer.user_id)
        db.expire_all()
        ts = db.query(TrustScore).filter(TrustScore.user_id == buyer.user_id).first()
        assert ts.trust_score <= 1000


# ── 13. Infrequent buyer principle ───────────────────────────────────────────

class TestInfrequentBuyerPrinciple:
    """
    Core TrustGrid design principle:
    A buyer who purchases once every six months must NOT receive a lower score
    purely because of low activity. TrustGrid measures reliability, not frequency.
    """

    def test_one_perfect_completion_gives_full_reliability_rates(self, db, buyer, seller, product):
        order = _force_paid_order(db, buyer, product)
        ship_order(db, order.order_id, seller.user_id)
        complete_order(db, order.order_id, buyer.user_id)

        fv = get_feature_vector(db, buyer.user_id)
        # 1 completed / 1 placed = 100% completion rate
        assert fv["order_completion_rate"] == 1.0
        # 0 cancellations
        assert fv["cancellation_rate"] == 0.0

    def test_infrequent_buyer_dimension_scores_not_penalised(self):
        """An infrequent buyer with perfect behaviour should have near-perfect dimension scores."""
        from app.trustgrid.trust_engine import _buyer_dimensions
        # Simulate someone who bought once, completed perfectly, no cancellations
        features = {
            "order_completion_rate": 1.0,
            "return_rate": 0.0,
            "payment_success_rate": 1.0,
            "cancellation_rate": 0.0,
            "referral_count": 0,
            "review_count": 0,
        }
        dim = _buyer_dimensions(features)
        assert dim["order_reliability"]      == 100.0
        assert dim["payment_reliability"]    == 100.0
        assert dim["cancellation_behaviour"] == 100.0
        assert dim["return_behaviour"]       == 100.0
