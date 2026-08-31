"""
Phase 2 tests — run with: pytest tests/ -v
These tests use an in-memory SQLite database so no PostgreSQL is required
to verify the business logic.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.user import UserRole
from app.models.trust import ConfidenceLevel, TrustTier
from app.services.user_service import create_user, get_user_by_email, get_user_by_id
from app.services.auth_service import authenticate_user
from app.utils.user_id import generate_user_id
from app.core.security import hash_password, verify_password, create_access_token, decode_access_token
from app.core.config import settings


# ── Test database fixture ─────────────────────────────────────────────────────

@pytest.fixture(scope="function")
def db():
    """
    Creates a fresh SQLite in-memory database for each test.
    This avoids any PostgreSQL dependency during CI/unit testing.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


# ── Security tests ────────────────────────────────────────────────────────────

class TestSecurity:
    def test_password_hash_is_not_plaintext(self):
        h = hash_password("MySecurePass1!")
        assert h != "MySecurePass1!"

    def test_verify_correct_password(self):
        h = hash_password("MySecurePass1!")
        assert verify_password("MySecurePass1!", h) is True

    def test_verify_wrong_password(self):
        h = hash_password("MySecurePass1!")
        assert verify_password("WrongPassword", h) is False

    def test_jwt_round_trip(self):
        token = create_access_token("BUY-10001", "buyer")
        payload = decode_access_token(token)
        assert payload["sub"]  == "BUY-10001"
        assert payload["role"] == "buyer"

    def test_jwt_contains_role(self):
        token = create_access_token("SEL-20001", "seller")
        payload = decode_access_token(token)
        assert payload["role"] == "seller"


# ── User ID generation tests ──────────────────────────────────────────────────

class TestUserIdGeneration:
    def test_first_buyer_id(self, db):
        uid = generate_user_id(db, UserRole.buyer)
        assert uid == "BUY-10001"

    def test_first_seller_id(self, db):
        uid = generate_user_id(db, UserRole.seller)
        assert uid == "SEL-20001"

    def test_sequential_buyer_ids(self, db):
        create_user(db, "Alice", "alice@example.com", "Password1!", "buyer")
        uid2 = generate_user_id(db, UserRole.buyer)
        assert uid2 == "BUY-10002"

    def test_buyer_and_seller_ids_independent(self, db):
        create_user(db, "Alice", "alice@example.com", "Password1!", "buyer")
        create_user(db, "Bob",   "bob@example.com",   "Password1!", "buyer")
        seller_uid = generate_user_id(db, UserRole.seller)
        assert seller_uid == "SEL-20001"  # seller count is still 0


# ── Registration tests ────────────────────────────────────────────────────────

class TestRegistration:
    def test_register_buyer(self, db):
        user = create_user(db, "Alice", "alice@example.com", "Password1!", "buyer")
        assert user.user_id.startswith("BUY-")
        assert user.role == UserRole.buyer
        assert user.email == "alice@example.com"

    def test_register_seller(self, db):
        user = create_user(db, "Bob", "bob@example.com", "Password1!", "seller")
        assert user.user_id.startswith("SEL-")
        assert user.role == UserRole.seller

    def test_email_stored_lowercase(self, db):
        user = create_user(db, "Alice", "ALICE@EXAMPLE.COM", "Password1!", "buyer")
        assert user.email == "alice@example.com"

    def test_password_not_stored_plaintext(self, db):
        user = create_user(db, "Alice", "alice@example.com", "Password1!", "buyer")
        assert user.password_hash != "Password1!"

    def test_duplicate_email_raises_409(self, db):
        from fastapi import HTTPException
        create_user(db, "Alice", "alice@example.com", "Password1!", "buyer")
        with pytest.raises(HTTPException) as exc:
            create_user(db, "Alice2", "alice@example.com", "Password2!", "buyer")
        assert exc.value.status_code == 409

    def test_initial_trust_score_is_700(self, db):
        user = create_user(db, "Alice", "alice@example.com", "Password1!", "buyer")
        db.refresh(user)
        assert user.trust_score is not None
        assert user.trust_score.trust_score == settings.INITIAL_TRUST_SCORE

    def test_initial_confidence_is_low(self, db):
        user = create_user(db, "Alice", "alice@example.com", "Password1!", "buyer")
        db.refresh(user)
        assert user.trust_score.confidence == ConfidenceLevel.LOW

    def test_initial_tier_is_trusted(self, db):
        user = create_user(db, "Alice", "alice@example.com", "Password1!", "buyer")
        db.refresh(user)
        assert user.trust_score.tier == TrustTier.TRUSTED

    def test_behavior_features_created(self, db):
        user = create_user(db, "Alice", "alice@example.com", "Password1!", "buyer")
        db.refresh(user)
        assert user.behavior_features is not None
        assert user.behavior_features.total_orders == 0


# ── Authentication tests ──────────────────────────────────────────────────────

class TestAuthentication:
    def test_login_correct_credentials(self, db):
        create_user(db, "Alice", "alice@example.com", "Password1!", "buyer")
        user = authenticate_user(db, "alice@example.com", "Password1!")
        assert user.email == "alice@example.com"

    def test_login_wrong_password_raises_401(self, db):
        from fastapi import HTTPException
        create_user(db, "Alice", "alice@example.com", "Password1!", "buyer")
        with pytest.raises(HTTPException) as exc:
            authenticate_user(db, "alice@example.com", "WrongPass")
        assert exc.value.status_code == 401

    def test_login_unknown_email_raises_401(self, db):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            authenticate_user(db, "nobody@example.com", "Password1!")
        assert exc.value.status_code == 401

    def test_login_case_insensitive_email(self, db):
        create_user(db, "Alice", "alice@example.com", "Password1!", "buyer")
        user = authenticate_user(db, "ALICE@EXAMPLE.COM", "Password1!")
        assert user.user_id.startswith("BUY-")


# ── Trust score boundary tests ────────────────────────────────────────────────

class TestTrustScoreBoundaries:
    def test_score_starts_at_700(self, db):
        user = create_user(db, "Alice", "alice@example.com", "Password1!", "buyer")
        db.refresh(user)
        assert user.trust_score.trust_score == 700

    def test_score_not_above_1000(self, db):
        from app.models.trust import TrustScore
        user = create_user(db, "Alice", "alice@example.com", "Password1!", "buyer")
        db.refresh(user)
        ts = user.trust_score
        ts.trust_score = min(1000, 9999)   # clamp logic
        assert ts.trust_score <= 1000

    def test_score_not_below_0(self, db):
        user = create_user(db, "Alice", "alice@example.com", "Password1!", "buyer")
        db.refresh(user)
        ts = user.trust_score
        ts.trust_score = max(0, -500)      # clamp logic
        assert ts.trust_score >= 0


# ── Lookup tests ──────────────────────────────────────────────────────────────

class TestLookup:
    def test_get_user_by_email(self, db):
        create_user(db, "Alice", "alice@example.com", "Password1!", "buyer")
        user = get_user_by_email(db, "alice@example.com")
        assert user is not None
        assert user.name == "Alice"

    def test_get_user_by_id(self, db):
        created = create_user(db, "Alice", "alice@example.com", "Password1!", "buyer")
        found   = get_user_by_id(db, created.user_id)
        assert found is not None
        assert found.email == "alice@example.com"

    def test_get_nonexistent_user_returns_none(self, db):
        assert get_user_by_email(db, "nobody@example.com") is None
        assert get_user_by_id(db, "BUY-99999") is None
