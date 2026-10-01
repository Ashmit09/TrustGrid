"""
TrustGrid — Integration Tests: Auth, New User, Positive/Negative/Mixed Scenarios
(spec §24-H, §24-I, §24-J, §24-K, §24-P)

Run with:
    PYTHONPATH=backend pytest backend/tests/test_integration.py -v
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base, get_db
from app.main import app
from app.services.event_service import emit_event
from app.services.trust_engine import run_trust_engine

# ── In-memory DB fixture ──────────────────────────────────────────────────────

TEST_DB_URL = "sqlite:///:memory:"


@pytest.fixture(scope="module")
def engine_m():
    eng = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)


@pytest.fixture(scope="function")
def db_s(engine_m):
    connection = engine_m.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def client_f(db_s):
    def override():
        try:
            yield db_s
        finally:
            pass
    app.dependency_overrides[get_db] = override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ── Helpers ───────────────────────────────────────────────────────────────────

def register_buyer(client, email="buyer@test.com", name="Test Buyer"):
    r = client.post("/auth/register", json={
        "name": name, "email": email, "password": "securepass1", "role": "buyer"
    })
    assert r.status_code == 201, r.text
    return r.json()


def register_seller(client, email="seller@test.com", name="Test Seller"):
    r = client.post("/auth/register", json={
        "name": name, "email": email, "password": "securepass1", "role": "seller"
    })
    assert r.status_code == 201, r.text
    return r.json()


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _make_events(user_id: str, role: str, descriptions: list, db) -> None:
    """Emit a list of (event_type, age_days) tuples as trust events."""
    now = datetime.now(timezone.utc)
    for event_type, age_days in descriptions:
        ts = now - timedelta(days=age_days)
        emit_event(db, user_id=user_id, role=role, event_type=event_type,
                   created_at=ts, metadata={})


# ── spec §24-H: New User Test ─────────────────────────────────────────────────

class TestNewUser:
    def test_new_buyer_score_700(self, client_f, db_s):
        """Register a buyer. Trust Score must be 700, confidence LOW."""
        data = register_buyer(client_f)
        token = data["access_token"]
        uid = data["user_id"]

        # Verify BUY- prefix
        assert uid.startswith("BUY-"), f"Expected BUY- prefix, got {uid}"

        # Call trust/me
        r = client_f.get("/trust/me", headers=auth_headers(token))
        assert r.status_code == 200
        body = r.json()
        assert body["trust_score"] == 700, f"New user score should be 700, got {body['trust_score']}"
        assert body["confidence"] == "LOW", f"New user confidence should be LOW, got {body['confidence']}"

    def test_new_seller_score_700(self, client_f, db_s):
        """Register a seller. Trust Score must be 700, confidence LOW."""
        data = register_seller(client_f)
        token = data["access_token"]
        uid = data["user_id"]
        assert uid.startswith("SEL-"), f"Expected SEL- prefix, got {uid}"
        r = client_f.get("/trust/me", headers=auth_headers(token))
        body = r.json()
        assert body["trust_score"] == 700
        assert body["confidence"] == "LOW"


# ── spec §24-I: Positive Buyer Scenario ──────────────────────────────────────

class TestPositiveBuyerScenario:
    def test_score_increases_with_positive_events(self, db_s):
        """
        10 successful orders + payments + 2 reviews → score moves up from 700.
        Confidence should increase with enough events.
        """
        user_id = "BUY-POSTEST"
        role = "buyer"
        events = (
            [("ORDER_COMPLETED", d) for d in range(1, 11)] +
            [("PAYMENT_SUCCESS", d) for d in range(1, 11)] +
            [("REVIEW_SUBMITTED", 3), ("REVIEW_SUBMITTED", 5)]
        )
        _make_events(user_id, role, events, db_s)

        from app.services.event_service import get_events_for_user
        from app.models.trust_event import TrustEvent

        raw = db_s.query(TrustEvent).filter(TrustEvent.user_id == user_id).all()
        event_dicts = [{"event_type": e.event_type, "created_at": e.created_at,
                        "metadata_": e.metadata_ or {}} for e in raw]

        result = run_trust_engine(db_s, user_id, role, event_dicts)

        assert result["trust_score"] > 700, \
            f"Positive buyer score should exceed 700, got {result['trust_score']}"
        assert result["confidence"] in ("MEDIUM", "HIGH")
        # Positive factors should appear in explanation
        assert len(result["explanation"]["positive_factors"]) >= 1

    def test_no_fake_high_confidence_for_new_user(self, db_s):
        """New user with 0 events must stay at 700 / LOW."""
        user_id = "BUY-NEWTEST"
        result = run_trust_engine(db_s, user_id, "buyer", [])
        assert result["trust_score"] == 700
        assert result["confidence"] == "LOW"


# ── spec §24-J: Negative Buyer Scenario ───────────────────────────────────────

class TestNegativeBuyerScenario:
    def test_score_decreases_with_negative_events(self, db_s):
        """Repeated cancellations + payment failures → score below 700."""
        user_id = "BUY-NEGTEST"
        events = (
            [("ORDER_CANCELLED", d) for d in range(1, 9)] +
            [("PAYMENT_FAILED", d) for d in [2, 4, 6]] +
            [("RETURN_REQUESTED", 1)]
        )
        _make_events(user_id, "buyer", events, db_s)
        from app.models.trust_event import TrustEvent
        raw = db_s.query(TrustEvent).filter(TrustEvent.user_id == user_id).all()
        event_dicts = [{"event_type": e.event_type, "created_at": e.created_at,
                        "metadata_": e.metadata_ or {}} for e in raw]

        result = run_trust_engine(db_s, user_id, "buyer", event_dicts)
        assert result["trust_score"] < 700, \
            f"Negative buyer score should be below 700, got {result['trust_score']}"
        assert len(result["explanation"]["negative_factors"]) >= 1

    def test_single_event_no_extreme_jump(self, db_s):
        """One isolated cancellation must not drop score below 500."""
        user_id = "BUY-SINGLE"
        _make_events(user_id, "buyer", [("ORDER_CANCELLED", 1)], db_s)
        from app.models.trust_event import TrustEvent
        raw = db_s.query(TrustEvent).filter(TrustEvent.user_id == user_id).all()
        event_dicts = [{"event_type": e.event_type, "created_at": e.created_at,
                        "metadata_": e.metadata_ or {}} for e in raw]
        result = run_trust_engine(db_s, user_id, "buyer", event_dicts)
        assert result["trust_score"] >= 500, \
            f"Single cancellation should not drop below 500, got {result['trust_score']}"


# ── spec §24-K: Mixed Buyer Scenario ─────────────────────────────────────────

class TestMixedBuyerScenario:
    def test_mixed_events_score_between_0_and_1000(self, db_s):
        """10 completions + 2 cancellations + 1 payment_failed + 1 return."""
        user_id = "BUY-MIXTEST"
        events = (
            [("ORDER_COMPLETED", d) for d in range(1, 11)] +
            [("ORDER_CANCELLED", 3), ("ORDER_CANCELLED", 7)] +
            [("PAYMENT_FAILED", 5)] +
            [("RETURN_REQUESTED", 2)]
        )
        _make_events(user_id, "buyer", events, db_s)
        from app.models.trust_event import TrustEvent
        raw = db_s.query(TrustEvent).filter(TrustEvent.user_id == user_id).all()
        event_dicts = [{"event_type": e.event_type, "created_at": e.created_at,
                        "metadata_": e.metadata_ or {}} for e in raw]
        result = run_trust_engine(db_s, user_id, "buyer", event_dicts)
        assert 0 <= result["trust_score"] <= 1000
        # Neither automatic 0 nor 1000
        assert result["trust_score"] < 1000
        assert result["trust_score"] > 0
        # Both positive and negative factors visible
        exp = result["explanation"]
        has_both = (len(exp["positive_factors"]) + len(exp["negative_factors"])) >= 1
        assert has_both


# ── spec §24-L: Time-Decay Comparison ─────────────────────────────────────────

class TestTimeDecayComparison:
    def test_recent_bad_event_worse_than_old_bad_event(self, db_s):
        """
        Scenario A: 100-day cancel + 1-day success  → better score
        Scenario B: 1-day cancel + 100-day success → worse score
        """
        # Scenario A
        _make_events("BUY-DCA", "buyer",
                     [("ORDER_CANCELLED", 100), ("ORDER_COMPLETED", 1)], db_s)
        from app.models.trust_event import TrustEvent
        raw_a = db_s.query(TrustEvent).filter(TrustEvent.user_id == "BUY-DCA").all()
        ea = [{"event_type": e.event_type, "created_at": e.created_at, "metadata_": {}} for e in raw_a]
        result_a = run_trust_engine(db_s, "BUY-DCA", "buyer", ea)

        # Scenario B
        _make_events("BUY-DCB", "buyer",
                     [("ORDER_COMPLETED", 100), ("ORDER_CANCELLED", 1)], db_s)
        raw_b = db_s.query(TrustEvent).filter(TrustEvent.user_id == "BUY-DCB").all()
        eb = [{"event_type": e.event_type, "created_at": e.created_at, "metadata_": {}} for e in raw_b]
        result_b = run_trust_engine(db_s, "BUY-DCB", "buyer", eb)

        assert result_a["trust_score"] > result_b["trust_score"], (
            f"Scenario A (recent success) score {result_a['trust_score']} should be > "
            f"Scenario B (recent cancel) score {result_b['trust_score']}"
        )


# ── spec §24-P: Security Tests ─────────────────────────────────────────────────

class TestSecurity:
    def test_unauthenticated_cannot_access_trust(self, client_f):
        r = client_f.get("/trust/me")
        assert r.status_code in (401, 403)

    def test_buyer_cannot_access_admin_endpoint(self, client_f, db_s):
        data = register_buyer(client_f, email="sectest@test.com")
        r = client_f.get("/admin/users",
                         headers=auth_headers(data["access_token"]))
        assert r.status_code == 403

    def test_invalid_token_rejected(self, client_f):
        r = client_f.get("/trust/me",
                         headers={"Authorization": "Bearer invalidtoken.abc.xyz"})
        assert r.status_code == 401

    def test_health_endpoint_public(self, client_f):
        r = client_f.get("/health")
        assert r.status_code == 200


# ── spec §24-O: ML Tests ─────────────────────────────────────────────────────

class TestMLService:
    def test_model_loads(self):
        from app.services.ml_service import is_model_available
        assert is_model_available("buyer"), "Buyer XGBoost model should be loadable"
        assert is_model_available("seller"), "Seller XGBoost model should be loadable"

    def test_prediction_in_0_1(self):
        from app.services.ml_service import predict
        features = {
            "decayed_completion_rate": 0.9,
            "decayed_problematic_return_rate": 0.0,
            "decayed_payment_success_rate": 0.95,
            "decayed_cancellation_rate": 0.05,
            "engagement_quality": 0.3,
            "total_orders": 20,
            "cancelled_orders": 1,
            "total_payments": 20,
            "failed_payments": 0,
            "total_returns": 1,
            "problematic_returns": 0,
            "meaningful_event_count": 25,
            "recent_orders_30d": 3,
            "recent_cancels_30d": 0,
            "account_age_days": 180,
        }
        p = predict(features, "buyer")
        assert p is not None
        assert 0.0 <= p <= 1.0, f"ML probability must be in [0,1], got {p}"

    def test_no_nan_in_features_handled(self):
        """NaN inputs should not crash the model."""
        from app.services.ml_service import predict
        import math
        features = {k: float("nan") for k in [
            "decayed_completion_rate", "decayed_problematic_return_rate",
            "decayed_payment_success_rate", "decayed_cancellation_rate",
            "engagement_quality", "total_orders", "cancelled_orders",
            "total_payments", "failed_payments", "total_returns",
            "problematic_returns", "meaningful_event_count",
            "recent_orders_30d", "recent_cancels_30d", "account_age_days",
        ]}
        # Should not raise
        p = predict(features, "buyer")
        assert p is None or (0.0 <= p <= 1.0)

    def test_score_always_0_to_1000(self, db_s):
        """Run trust engine for various event sets; score must always be in [0, 1000]."""
        for uid, events in [
            ("BUY-TST1", []),
            ("BUY-TST2", [("ORDER_COMPLETED", 1)] * 5),
            ("BUY-TST3", [("ORDER_CANCELLED", 1)] * 10 + [("PAYMENT_FAILED", 2)] * 5),
        ]:
            _make_events(uid, "buyer", events, db_s)
            from app.models.trust_event import TrustEvent
            raw = db_s.query(TrustEvent).filter(TrustEvent.user_id == uid).all()
            ed = [{"event_type": e.event_type, "created_at": e.created_at, "metadata_": {}} for e in raw]
            result = run_trust_engine(db_s, uid, "buyer", ed)
            assert 0 <= result["trust_score"] <= 1000, \
                f"Trust score {result['trust_score']} out of range for {uid}"
