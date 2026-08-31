-- =============================================================================
-- TrustGrid — PostgreSQL Schema
-- =============================================================================
-- Generated from SQLAlchemy ORM models.
-- Compatible with PostgreSQL 14+.
-- Run against an empty database:
--   psql -U trustgrid_user -d trustgrid_db -f schema.sql
-- =============================================================================


-- ── Enums ─────────────────────────────────────────────────────────────────────

CREATE TYPE userrole        AS ENUM ('buyer', 'seller', 'admin');
CREATE TYPE confidencelevel AS ENUM ('LOW', 'MEDIUM', 'HIGH');
CREATE TYPE trusttier       AS ENUM ('RESTRICTED', 'STANDARD', 'TRUSTED', 'ELITE');
CREATE TYPE orderstatus     AS ENUM ('pending', 'paid', 'shipped', 'delivered', 'completed', 'cancelled', 'returned');
CREATE TYPE paymentstatus   AS ENUM ('success', 'failed');
CREATE TYPE returnstatus    AS ENUM ('pending', 'resolved', 'rejected');


-- ── users ─────────────────────────────────────────────────────────────────────
-- Central identity table. user_id (BUY-xxxxx / SEL-xxxxx) is the logical key.

CREATE TABLE users (
    id            SERIAL          PRIMARY KEY,
    user_id       VARCHAR(20)     NOT NULL UNIQUE,
    name          VARCHAR(120)    NOT NULL,
    email         VARCHAR(255)    NOT NULL UNIQUE,
    password_hash VARCHAR(255)    NOT NULL,
    role          userrole        NOT NULL DEFAULT 'buyer',
    created_at    TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_users_user_id ON users (user_id);
CREATE INDEX ix_users_email   ON users (email);


-- ── products ──────────────────────────────────────────────────────────────────

CREATE TABLE products (
    id          SERIAL          PRIMARY KEY,
    seller_id   VARCHAR(20)     NOT NULL REFERENCES users (user_id),
    title       VARCHAR(255)    NOT NULL,
    description TEXT,
    price       NUMERIC(10, 2)  NOT NULL,
    stock       INTEGER         NOT NULL DEFAULT 0,
    category    VARCHAR(100),
    image_url   VARCHAR(500),
    is_active   BOOLEAN         NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_products_seller_id ON products (seller_id);


-- ── orders ────────────────────────────────────────────────────────────────────

CREATE TABLE orders (
    id           SERIAL          PRIMARY KEY,
    order_id     VARCHAR(30)     NOT NULL UNIQUE,
    buyer_id     VARCHAR(20)     NOT NULL REFERENCES users (user_id),
    seller_id    VARCHAR(20)     NOT NULL REFERENCES users (user_id),
    product_id   INTEGER         NOT NULL REFERENCES products (id),
    quantity     INTEGER         NOT NULL DEFAULT 1,
    unit_price   NUMERIC(10, 2)  NOT NULL,
    total_amount NUMERIC(10, 2)  NOT NULL,
    status       orderstatus     NOT NULL DEFAULT 'pending',
    created_at   TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX ix_orders_order_id  ON orders (order_id);
CREATE INDEX ix_orders_buyer_id  ON orders (buyer_id);
CREATE INDEX ix_orders_seller_id ON orders (seller_id);


-- ── payments ──────────────────────────────────────────────────────────────────

CREATE TABLE payments (
    id         SERIAL          PRIMARY KEY,
    order_id   VARCHAR(30)     NOT NULL REFERENCES orders (order_id),
    buyer_id   VARCHAR(20)     NOT NULL REFERENCES users (user_id),
    amount     NUMERIC(10, 2)  NOT NULL,
    status     paymentstatus   NOT NULL,
    created_at TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_payments_order_id ON payments (order_id);
CREATE INDEX ix_payments_buyer_id ON payments (buyer_id);


-- ── returns ───────────────────────────────────────────────────────────────────

CREATE TABLE returns (
    id          SERIAL        PRIMARY KEY,
    order_id    VARCHAR(30)   NOT NULL REFERENCES orders (order_id),
    buyer_id    VARCHAR(20)   NOT NULL REFERENCES users (user_id),
    seller_id   VARCHAR(20)   NOT NULL REFERENCES users (user_id),
    reason      TEXT,
    status      returnstatus  NOT NULL DEFAULT 'pending',
    created_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);

CREATE INDEX ix_returns_order_id  ON returns (order_id);
CREATE INDEX ix_returns_buyer_id  ON returns (buyer_id);
CREATE INDEX ix_returns_seller_id ON returns (seller_id);


-- ── reviews ───────────────────────────────────────────────────────────────────

CREATE TABLE reviews (
    id          SERIAL       PRIMARY KEY,
    order_id    VARCHAR(30)  NOT NULL REFERENCES orders (order_id),
    reviewer_id VARCHAR(20)  NOT NULL REFERENCES users (user_id),
    seller_id   VARCHAR(20)  NOT NULL REFERENCES users (user_id),
    rating      INTEGER      NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment     TEXT,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_reviews_order_id   ON reviews (order_id);
CREATE INDEX ix_reviews_reviewer_id ON reviews (reviewer_id);
CREATE INDEX ix_reviews_seller_id  ON reviews (seller_id);


-- ── referrals ─────────────────────────────────────────────────────────────────

CREATE TABLE referrals (
    id          SERIAL       PRIMARY KEY,
    referrer_id VARCHAR(20)  NOT NULL REFERENCES users (user_id),
    referred_id VARCHAR(20)  NOT NULL REFERENCES users (user_id),
    status      VARCHAR(20)  NOT NULL DEFAULT 'pending',
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_referrals_referrer_id ON referrals (referrer_id);
CREATE INDEX ix_referrals_referred_id ON referrals (referred_id);


-- ── trust_events ──────────────────────────────────────────────────────────────
-- Immutable append-only event log. Never updated or deleted.
-- event_id: UUID-style unique key per event.

CREATE TABLE trust_events (
    id             SERIAL       PRIMARY KEY,
    event_id       VARCHAR(50)  NOT NULL UNIQUE,
    user_id        VARCHAR(20)  NOT NULL REFERENCES users (user_id),
    event_type     VARCHAR(60)  NOT NULL,
    reference_id   VARCHAR(50),                 -- optional: order_id, product_id, etc.
    metadata       JSONB,                        -- arbitrary event context
    impact_summary VARCHAR(255),
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_trust_events_event_id   ON trust_events (event_id);
CREATE INDEX ix_trust_events_user_id    ON trust_events (user_id);
CREATE INDEX ix_trust_events_created_at ON trust_events (created_at);


-- ── behavior_features ─────────────────────────────────────────────────────────
-- Materialized feature vector. One row per user. Updated on every trust event.
-- All rate fields are in [0.0, 1.0]. Count fields are non-negative integers.

CREATE TABLE behavior_features (
    id                       SERIAL       PRIMARY KEY,
    user_id                  VARCHAR(20)  NOT NULL UNIQUE REFERENCES users (user_id),

    -- Buyer features
    total_orders             INTEGER      NOT NULL DEFAULT 0,
    completed_orders         INTEGER      NOT NULL DEFAULT 0,
    order_completion_rate    FLOAT        NOT NULL DEFAULT 0.0,
    total_returns            INTEGER      NOT NULL DEFAULT 0,
    return_rate              FLOAT        NOT NULL DEFAULT 0.0,
    payment_attempts         INTEGER      NOT NULL DEFAULT 0,
    successful_payments      INTEGER      NOT NULL DEFAULT 0,
    payment_success_rate     FLOAT        NOT NULL DEFAULT 1.0,
    total_cancellations      INTEGER      NOT NULL DEFAULT 0,
    cancellation_rate        FLOAT        NOT NULL DEFAULT 0.0,
    referral_count           INTEGER      NOT NULL DEFAULT 0,
    review_count             INTEGER      NOT NULL DEFAULT 0,

    -- Seller features
    fulfilled_orders         INTEGER      NOT NULL DEFAULT 0,
    seller_cancellations     INTEGER      NOT NULL DEFAULT 0,
    fulfillment_rate         FLOAT        NOT NULL DEFAULT 1.0,
    on_time_deliveries       INTEGER      NOT NULL DEFAULT 0,
    late_deliveries          INTEGER      NOT NULL DEFAULT 0,
    late_delivery_rate       FLOAT        NOT NULL DEFAULT 0.0,
    avg_rating_received      FLOAT        NOT NULL DEFAULT 0.0,
    return_requests_received INTEGER      NOT NULL DEFAULT 0,
    returns_responded        INTEGER      NOT NULL DEFAULT 0,
    return_response_rate     FLOAT        NOT NULL DEFAULT 1.0,
    products_listed          INTEGER      NOT NULL DEFAULT 0,

    -- Evidence meta
    decayed_event_weight     FLOAT        NOT NULL DEFAULT 0.0,
    updated_at               TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_behavior_features_user_id ON behavior_features (user_id);


-- ── trust_scores ──────────────────────────────────────────────────────────────
-- Single live row per user. Updated on every trust recalculation.
-- dim_scores stores per-dimension JSON: {"order_reliability": 92.0, ...}

CREATE TABLE trust_scores (
    id           SERIAL          PRIMARY KEY,
    user_id      VARCHAR(20)     NOT NULL UNIQUE REFERENCES users (user_id),
    trust_score  INTEGER         NOT NULL DEFAULT 700,
    confidence   confidencelevel NOT NULL DEFAULT 'LOW',
    tier         trusttier       NOT NULL DEFAULT 'TRUSTED',
    dim_scores   JSONB,
    last_updated TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_trust_scores_user_id ON trust_scores (user_id);


-- ── score_history ─────────────────────────────────────────────────────────────
-- Append-only audit trail of every trust score change.

CREATE TABLE score_history (
    id           SERIAL       PRIMARY KEY,
    user_id      VARCHAR(20)  NOT NULL REFERENCES users (user_id),
    old_score    INTEGER      NOT NULL,
    new_score    INTEGER      NOT NULL,
    score_change INTEGER      NOT NULL,
    reason       VARCHAR(255),
    event_type   VARCHAR(60),
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_score_history_user_id    ON score_history (user_id);
CREATE INDEX ix_score_history_created_at ON score_history (created_at);


-- ── privileges ────────────────────────────────────────────────────────────────
-- Current benefit/privilege state per user.
-- status: 'active' | 'inactive'

CREATE TABLE privileges (
    id             SERIAL       PRIMARY KEY,
    user_id        VARCHAR(20)  NOT NULL REFERENCES users (user_id),
    privilege_name VARCHAR(100) NOT NULL,
    status         VARCHAR(20)  NOT NULL DEFAULT 'inactive',
    reason         VARCHAR(255),
    updated_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_privileges_user_id ON privileges (user_id);
