"""
Phase 3 tests — marketplace: products, orders, payment, returns, reviews.
Uses in-memory SQLite (no PostgreSQL required).
"""
import pytest
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException

from app.db.base import Base
from app.models.user import UserRole
from app.models.marketplace import OrderStatus, PaymentStatus, ReturnStatus
from app.services.user_service import create_user
from app.services.product_service import (
    create_product, get_product, list_products, update_product, get_seller_products
)
from app.services.order_service import (
    place_order, cancel_order, ship_order, complete_order,
    request_return, submit_review, get_orders_for_user,
)
from app.schemas.product import ProductCreate, ProductUpdate
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
    return create_user(db, "Alice Buyer", "alice@test.com", "Password1!", "buyer")


@pytest.fixture
def seller(db):
    return create_user(db, "Bob Seller", "bob@test.com", "Password1!", "seller")


@pytest.fixture
def product(db, seller):
    return create_product(db, seller.user_id, ProductCreate(
        title="Test Widget",
        description="A fine widget",
        price=Decimal("199.99"),
        stock=50,
        category="Electronics",
    ))


@pytest.fixture
def paid_order(db, buyer, product):
    """Returns a successfully paid order (may occasionally fail due to 95% payment sim)."""
    import random
    random.seed(42)  # seed for deterministic 'success' in tests
    return place_order(db, buyer.user_id, OrderCreate(product_id=product.id, quantity=1))


# ── Product tests ─────────────────────────────────────────────────────────────

class TestProducts:
    def test_create_product(self, db, seller):
        p = create_product(db, seller.user_id, ProductCreate(
            title="Gadget", price=Decimal("99.00"), stock=10
        ))
        assert p.id is not None
        assert p.seller_id == seller.user_id
        assert p.title == "Gadget"

    def test_get_product(self, db, product):
        fetched = get_product(db, product.id)
        assert fetched.id == product.id
        assert fetched.title == "Test Widget"

    def test_get_nonexistent_product_raises_404(self, db):
        with pytest.raises(HTTPException) as exc:
            get_product(db, 99999)
        assert exc.value.status_code == 404

    def test_list_products_returns_active(self, db, product):
        products = list_products(db)
        assert any(p.id == product.id for p in products)

    def test_list_products_search(self, db, product):
        results = list_products(db, search="Widget")
        assert len(results) == 1
        results_none = list_products(db, search="xyz_not_exist")
        assert len(results_none) == 0

    def test_update_product_by_owner(self, db, seller, product):
        updated = update_product(db, product.id, seller.user_id, ProductUpdate(title="New Title"))
        assert updated.title == "New Title"

    def test_update_product_by_non_owner_raises_403(self, db, product):
        with pytest.raises(HTTPException) as exc:
            update_product(db, product.id, "SEL-99999", ProductUpdate(title="Hack"))
        assert exc.value.status_code == 403

    def test_seller_products_list(self, db, seller, product):
        items = get_seller_products(db, seller.user_id)
        assert len(items) == 1
        assert items[0].seller_id == seller.user_id


# ── Order placement tests ─────────────────────────────────────────────────────

class TestOrderPlacement:
    def test_place_order_creates_order(self, db, buyer, product):
        import random; random.seed(42)
        order = place_order(db, buyer.user_id, OrderCreate(product_id=product.id, quantity=2))
        assert order.order_id.startswith("ORD-")
        assert order.buyer_id == buyer.user_id
        assert order.seller_id == product.seller_id
        assert order.quantity == 2

    def test_place_order_decrements_stock_on_success(self, db, buyer, product):
        import random; random.seed(42)
        initial_stock = product.stock
        order = place_order(db, buyer.user_id, OrderCreate(product_id=product.id, quantity=3))
        db.refresh(product)
        if order.status == OrderStatus.paid:
            assert product.stock == initial_stock - 3
        else:
            # payment failed — stock should be unchanged
            assert product.stock == initial_stock

    def test_cannot_buy_own_product(self, db, seller, product):
        with pytest.raises(HTTPException) as exc:
            place_order(db, seller.user_id, OrderCreate(product_id=product.id, quantity=1))
        assert exc.value.status_code == 400

    def test_insufficient_stock_raises_400(self, db, buyer, product):
        # quantity=999 exceeds schema max (100), so test with a value that passes schema
        # but exceeds stock (product has 50 units, so 51 is a valid schema value but OOS)
        with pytest.raises(HTTPException) as exc:
            place_order(db, buyer.user_id, OrderCreate(product_id=product.id, quantity=51))
        assert exc.value.status_code == 400

    def test_nonexistent_product_raises_404(self, db, buyer):
        with pytest.raises(HTTPException) as exc:
            place_order(db, buyer.user_id, OrderCreate(product_id=99999, quantity=1))
        assert exc.value.status_code == 404


# ── Order lifecycle tests ─────────────────────────────────────────────────────

class TestOrderLifecycle:
    def _make_paid_order(self, db, buyer, product):
        """Force a paid order by mocking payment."""
        import random; random.seed(42)
        from app.models.marketplace import Order, Payment
        order = place_order(db, buyer.user_id, OrderCreate(product_id=product.id, quantity=1))
        # Ensure paid status for downstream tests
        if order.status != OrderStatus.paid:
            order.status = OrderStatus.paid
            db.commit(); db.refresh(order)
        return order

    def test_cancel_paid_order_by_buyer(self, db, buyer, product):
        order = self._make_paid_order(db, buyer, product)
        cancelled = cancel_order(db, order.order_id, buyer.user_id, "buyer")
        assert cancelled.status == OrderStatus.cancelled

    def test_buyer_cannot_cancel_others_order(self, db, buyer, seller, product):
        order = self._make_paid_order(db, buyer, product)
        with pytest.raises(HTTPException) as exc:
            cancel_order(db, order.order_id, seller.user_id, "buyer")
        assert exc.value.status_code == 403

    def test_ship_order_by_seller(self, db, buyer, seller, product):
        order = self._make_paid_order(db, buyer, product)
        shipped = ship_order(db, order.order_id, seller.user_id)
        assert shipped.status == OrderStatus.shipped

    def test_complete_order_by_buyer(self, db, buyer, seller, product):
        order = self._make_paid_order(db, buyer, product)
        ship_order(db, order.order_id, seller.user_id)
        completed = complete_order(db, order.order_id, buyer.user_id)
        assert completed.status == OrderStatus.completed
        assert completed.completed_at is not None

    def test_cannot_complete_unshipped_order(self, db, buyer, product):
        order = self._make_paid_order(db, buyer, product)
        with pytest.raises(HTTPException) as exc:
            complete_order(db, order.order_id, buyer.user_id)
        assert exc.value.status_code == 400


# ── Return tests ──────────────────────────────────────────────────────────────

class TestReturns:
    def _make_completed_order(self, db, buyer, seller, product):
        import random; random.seed(42)
        order = place_order(db, buyer.user_id, OrderCreate(product_id=product.id, quantity=1))
        if order.status != OrderStatus.paid:
            order.status = OrderStatus.paid; db.commit(); db.refresh(order)
        ship_order(db, order.order_id, seller.user_id)
        complete_order(db, order.order_id, buyer.user_id)
        db.refresh(order)
        return order

    def test_request_return_on_completed_order(self, db, buyer, seller, product):
        order = self._make_completed_order(db, buyer, seller, product)
        ret = request_return(db, order.order_id, buyer.user_id, ReturnCreate(reason="Wrong item"))
        assert ret.status == ReturnStatus.pending
        assert ret.buyer_id == buyer.user_id

    def test_duplicate_return_raises_409(self, db, buyer, seller, product):
        order = self._make_completed_order(db, buyer, seller, product)
        # After request_return, order status becomes 'returned' — refresh
        request_return(db, order.order_id, buyer.user_id, ReturnCreate(reason="First"))
        db.refresh(order)   # order is now OrderStatus.returned
        with pytest.raises(HTTPException) as exc:
            request_return(db, order.order_id, buyer.user_id, ReturnCreate(reason="Second"))
        assert exc.value.status_code == 409

    def test_cannot_return_paid_order(self, db, buyer, product):
        import random; random.seed(42)
        order = place_order(db, buyer.user_id, OrderCreate(product_id=product.id, quantity=1))
        if order.status != OrderStatus.paid:
            order.status = OrderStatus.paid; db.commit(); db.refresh(order)
        with pytest.raises(HTTPException) as exc:
            request_return(db, order.order_id, buyer.user_id, ReturnCreate())
        assert exc.value.status_code == 400


# ── Review tests ──────────────────────────────────────────────────────────────

class TestReviews:
    def _make_completed_order(self, db, buyer, seller, product):
        import random; random.seed(42)
        order = place_order(db, buyer.user_id, OrderCreate(product_id=product.id, quantity=1))
        if order.status != OrderStatus.paid:
            order.status = OrderStatus.paid; db.commit(); db.refresh(order)
        ship_order(db, order.order_id, seller.user_id)
        complete_order(db, order.order_id, buyer.user_id)
        db.refresh(order)
        return order

    def test_submit_review_on_completed_order(self, db, buyer, seller, product):
        order = self._make_completed_order(db, buyer, seller, product)
        review = submit_review(db, order.order_id, buyer.user_id, ReviewCreate(rating=5, comment="Great!"))
        assert review.rating == 5
        assert review.reviewer_id == buyer.user_id

    def test_duplicate_review_raises_409(self, db, buyer, seller, product):
        order = self._make_completed_order(db, buyer, seller, product)
        submit_review(db, order.order_id, buyer.user_id, ReviewCreate(rating=4))
        with pytest.raises(HTTPException) as exc:
            submit_review(db, order.order_id, buyer.user_id, ReviewCreate(rating=3))
        assert exc.value.status_code == 409

    def test_review_rating_range(self, db, buyer, seller, product):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ReviewCreate(rating=6)
        with pytest.raises(ValidationError):
            ReviewCreate(rating=0)

    def test_cannot_review_uncompleted_order(self, db, buyer, product):
        import random; random.seed(42)
        order = place_order(db, buyer.user_id, OrderCreate(product_id=product.id, quantity=1))
        if order.status != OrderStatus.paid:
            order.status = OrderStatus.paid; db.commit(); db.refresh(order)
        with pytest.raises(HTTPException) as exc:
            submit_review(db, order.order_id, buyer.user_id, ReviewCreate(rating=5))
        assert exc.value.status_code == 400


# ── Order listing tests ───────────────────────────────────────────────────────

class TestOrderListing:
    def test_buyer_sees_own_orders(self, db, buyer, product):
        import random; random.seed(42)
        place_order(db, buyer.user_id, OrderCreate(product_id=product.id, quantity=1))
        orders = get_orders_for_user(db, buyer.user_id, "buyer")
        assert len(orders) == 1

    def test_seller_sees_own_orders(self, db, buyer, seller, product):
        import random; random.seed(42)
        place_order(db, buyer.user_id, OrderCreate(product_id=product.id, quantity=1))
        orders = get_orders_for_user(db, seller.user_id, "seller")
        assert len(orders) == 1
