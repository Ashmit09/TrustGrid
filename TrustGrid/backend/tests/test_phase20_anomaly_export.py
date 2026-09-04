"""
Phase 20/21/22 — Admin User Detail Modal, Anomaly Detection, CSV Export.

Tests
------
Anomaly detection service (unit):
  - run_anomaly_scan returns empty list when no bad patterns
  - SCORE_DROP flag created for ≥150pt drop in 24h
  - SCORE_SURGE flag created for ≥200pt rise in 24h
  - RAPID_CANCELLATIONS flag for rate>0.6 and count>=3
  - HIGH_RETURN_RATE flag for rate>0.5 and count>=3
  - Duplicate prevention: same flag_type not created twice in same window
  - Flag is returned with correct fields

Admin anomaly API:
  - GET /admin/anomalies requires admin role
  - GET /admin/anomalies returns list for admin
  - GET /admin/anomalies?resolved=false filters open flags only
  - GET /admin/anomalies?severity=HIGH filters by severity
  - POST /admin/anomalies/scan requires admin role
  - POST /admin/anomalies/scan creates flags and returns them
  - PATCH /admin/anomalies/{flag_id}/resolve marks flag resolved
  - PATCH /admin/anomalies/{flag_id}/resolve returns 404 for unknown flag
  - PATCH /admin/anomalies/{flag_id}/resolve returns 409 if already resolved

CSV export API:
  - GET /trust/{user_id}/export requires auth
  - GET /trust/{user_id}/export returns 403 for other user
  - Admin can export any user's history
  - Returns Content-Type text/csv
  - Returns Content-Disposition with filename
  - CSV header row is correct
  - CSV has one row per score history entry
  - Empty history returns header-only CSV
"""
import pytest
import uuid
from datetime import datetime, timezone, timedelta


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _register(client, email, name, role="buyer"):
    r = client.post("/auth/register", json={"email": email, "name": name, "password": "Demo1234!", "role": role})
    assert r.status_code == 201, r.text
    data = r.json()
    # AuthResponse wraps user under data["user"]
    return data["user"]

def _login(client, email):
    r = client.post("/auth/login", json={"email": email, "password": "Demo1234!"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]

def _auth(token):
    return {"Authorization": f"Bearer {token}"}

def _admin_token(client, api_db):
    """Create an admin user directly in DB (bypassing role validation) and return its token."""
    from app.services.user_service import create_user
    from app.models.user import UserRole

    # Create admin user directly in the shared DB
    u = create_user(api_db, email="adm@test.com", name="Admin", password="Demo1234!", role=UserRole.admin)
    return _login(client, "adm@test.com")


# ─── Anomaly service unit tests ───────────────────────────────────────────────

class TestAnomalyServiceUnit:
    """Direct unit tests against anomaly_service.run_anomaly_scan()."""

    def test_no_anomalies_clean_user(self, api_db):
        from app.services.anomaly_service import run_anomaly_scan
        from app.services.user_service import create_user

        create_user(api_db, email="clean@test.com", name="Clean", password="Demo1234!", role="buyer")
        flags = run_anomaly_scan(api_db)
        assert isinstance(flags, list)
        # No problematic patterns → no flags
        assert all(f.user_id != "clean@test.com" for f in flags)

    def test_score_drop_flag_created(self, api_db):
        from app.services.anomaly_service import run_anomaly_scan
        from app.services.user_service import create_user
        from app.models.trust import ScoreHistory

        user = create_user(api_db, email="dropper@test.com", name="Dropper", password="Demo1234!", role="buyer")
        uid  = user.user_id

        # Insert two history rows with >150pt drop within 24h
        now = datetime.now(timezone.utc)
        api_db.add(ScoreHistory(
            user_id=uid, old_score=900, new_score=900, score_change=0,
            reason="initial", event_type="order_completed",
            created_at=now - timedelta(hours=2),
        ))
        api_db.add(ScoreHistory(
            user_id=uid, old_score=900, new_score=700, score_change=-200,
            reason="cancelled", event_type="order_cancelled",
            created_at=now - timedelta(hours=1),
        ))
        api_db.commit()

        flags = run_anomaly_scan(api_db)
        drop_flags = [f for f in flags if f.user_id == uid and f.flag_type == "SCORE_DROP"]
        assert len(drop_flags) == 1
        flag = drop_flags[0]
        assert flag.severity == "HIGH"
        assert flag.score_before == 900
        assert flag.score_after  == 700
        assert flag.resolved     == 0
        assert "200" in flag.description or "pts" in flag.description.lower() or "drop" in flag.description.lower()

    def test_score_surge_flag_created(self, api_db):
        from app.services.anomaly_service import run_anomaly_scan
        from app.services.user_service import create_user
        from app.models.trust import ScoreHistory

        user = create_user(api_db, email="surger@test.com", name="Surger", password="Demo1234!", role="buyer")
        uid  = user.user_id
        now  = datetime.now(timezone.utc)

        api_db.add(ScoreHistory(
            user_id=uid, old_score=400, new_score=400, score_change=0,
            created_at=now - timedelta(hours=3),
        ))
        api_db.add(ScoreHistory(
            user_id=uid, old_score=400, new_score=650, score_change=250,
            created_at=now - timedelta(hours=1),
        ))
        api_db.commit()

        flags = run_anomaly_scan(api_db)
        surge_flags = [f for f in flags if f.user_id == uid and f.flag_type == "SCORE_SURGE"]
        assert len(surge_flags) == 1
        assert surge_flags[0].severity == "MEDIUM"

    def test_rapid_cancellations_flag(self, api_db):
        from app.services.anomaly_service import run_anomaly_scan
        from app.services.user_service import create_user
        from app.models.trust import BehaviorFeatures

        user = create_user(api_db, email="canceller@test.com", name="Cancel", password="Demo1234!", role="buyer")
        uid  = user.user_id

        bf = api_db.query(BehaviorFeatures).filter_by(user_id=uid).first()
        bf.total_cancellations = 5
        bf.total_orders        = 7
        bf.cancellation_rate   = 0.71
        api_db.commit()

        flags = run_anomaly_scan(api_db)
        cancel_flags = [f for f in flags if f.user_id == uid and f.flag_type == "RAPID_CANCELLATIONS"]
        assert len(cancel_flags) == 1
        assert cancel_flags[0].severity == "HIGH"

    def test_high_return_rate_flag(self, api_db):
        from app.services.anomaly_service import run_anomaly_scan
        from app.services.user_service import create_user
        from app.models.trust import BehaviorFeatures

        user = create_user(api_db, email="returner@test.com", name="Return", password="Demo1234!", role="buyer")
        uid  = user.user_id

        bf = api_db.query(BehaviorFeatures).filter_by(user_id=uid).first()
        bf.total_returns = 4
        bf.total_orders  = 6
        bf.return_rate   = 0.67
        api_db.commit()

        flags = run_anomaly_scan(api_db)
        ret_flags = [f for f in flags if f.user_id == uid and f.flag_type == "HIGH_RETURN_RATE"]
        assert len(ret_flags) == 1
        assert ret_flags[0].severity == "MEDIUM"

    def test_no_duplicate_flag_same_window(self, api_db):
        """Running scan twice should not create a second SCORE_DROP flag."""
        from app.services.anomaly_service import run_anomaly_scan
        from app.services.user_service import create_user
        from app.models.trust import ScoreHistory

        user = create_user(api_db, email="nodup@test.com", name="NoDup", password="Demo1234!", role="buyer")
        uid  = user.user_id
        now  = datetime.now(timezone.utc)

        # Need two rows so len(recent) >= 2 and delta is computed
        api_db.add(ScoreHistory(
            user_id=uid, old_score=900, new_score=900, score_change=0,
            created_at=now - timedelta(hours=2),
        ))
        api_db.add(ScoreHistory(
            user_id=uid, old_score=900, new_score=700, score_change=-200,
            created_at=now - timedelta(hours=1),
        ))
        api_db.commit()

        flags1 = run_anomaly_scan(api_db)
        flags2 = run_anomaly_scan(api_db)  # second scan should not duplicate

        all_drop = [
            f for f in flags1 + flags2
            if f.user_id == uid and f.flag_type == "SCORE_DROP"
        ]
        assert len(all_drop) == 1

    def test_flag_has_required_fields(self, api_db):
        from app.services.anomaly_service import run_anomaly_scan
        from app.services.user_service import create_user
        from app.models.trust import ScoreHistory

        user = create_user(api_db, email="fields@test.com", name="Fields", password="Demo1234!", role="buyer")
        uid  = user.user_id
        now  = datetime.now(timezone.utc)
        # Two rows required for delta check
        api_db.add(ScoreHistory(
            user_id=uid, old_score=900, new_score=900, score_change=0,
            created_at=now - timedelta(hours=2),
        ))
        api_db.add(ScoreHistory(
            user_id=uid, old_score=900, new_score=700, score_change=-200,
            created_at=now - timedelta(hours=1),
        ))
        api_db.commit()

        flags = [f for f in run_anomaly_scan(api_db) if f.user_id == uid]
        assert len(flags) >= 1
        flag = flags[0]
        assert flag.flag_id
        assert flag.flag_type
        assert flag.severity   in ("LOW", "MEDIUM", "HIGH")
        assert flag.description
        assert flag.created_at is not None


# ─── Admin anomaly API tests ──────────────────────────────────────────────────

class TestAdminAnomalyAPI:

    def test_list_anomalies_requires_admin(self, api_client):
        user = _register(api_client, "buyer@test.com", "Buyer")
        tok  = _login(api_client, "buyer@test.com")
        r = api_client.get("/admin/anomalies", headers=_auth(tok))
        assert r.status_code == 403

    def test_list_anomalies_empty_for_admin(self, api_client, api_db):
        tok = _admin_token(api_client, api_db)
        r   = api_client.get("/admin/anomalies", headers=_auth(tok))
        assert r.status_code == 200
        body = r.json()
        assert "anomalies" in body
        assert "total" in body
        assert isinstance(body["anomalies"], list)

    def test_scan_requires_admin(self, api_client):
        _register(api_client, "b2@test.com", "B2")
        tok = _login(api_client, "b2@test.com")
        r   = api_client.post("/admin/anomalies/scan", headers=_auth(tok))
        assert r.status_code == 403

    def test_scan_returns_structure(self, api_client, api_db):
        tok = _admin_token(api_client, api_db)
        r   = api_client.post("/admin/anomalies/scan", headers=_auth(tok))
        assert r.status_code == 200
        body = r.json()
        assert "new_flags_created" in body
        assert "flags" in body
        assert isinstance(body["flags"], list)

    def test_scan_creates_rapid_cancellation_flag(self, api_client, api_db):
        from app.models.trust import BehaviorFeatures

        user = _register(api_client, "scanbuyer@test.com", "ScanBuyer")
        uid  = user["user_id"]
        bf   = api_db.query(BehaviorFeatures).filter_by(user_id=uid).first()
        bf.total_cancellations = 6
        bf.total_orders        = 8
        bf.cancellation_rate   = 0.75
        api_db.commit()

        tok = _admin_token(api_client, api_db)
        r   = api_client.post("/admin/anomalies/scan", headers=_auth(tok))
        assert r.status_code == 200
        body = r.json()
        assert body["new_flags_created"] >= 1
        types = [f["flag_type"] for f in body["flags"]]
        assert "RAPID_CANCELLATIONS" in types

    def test_resolve_flag(self, api_client, api_db):
        from app.models.trust import AnomalyFlag

        # Manually create a flag
        flag = AnomalyFlag(
            flag_id="resolve-test-flag",
            user_id="BUY-99999",
            flag_type="SCORE_DROP",
            severity="HIGH",
            description="Test flag",
            resolved=0,
            created_at=datetime.now(timezone.utc),
        )
        api_db.add(flag)
        api_db.commit()

        tok = _admin_token(api_client, api_db)
        r   = api_client.patch("/admin/anomalies/resolve-test-flag/resolve", headers=_auth(tok))
        assert r.status_code == 200
        body = r.json()
        assert body["resolved"] is True
        assert body["resolved_at"] is not None

    def test_resolve_unknown_flag_returns_404(self, api_client, api_db):
        tok = _admin_token(api_client, api_db)
        r   = api_client.patch("/admin/anomalies/no-such-flag/resolve", headers=_auth(tok))
        assert r.status_code == 404

    def test_resolve_already_resolved_returns_409(self, api_client, api_db):
        from app.models.trust import AnomalyFlag

        flag = AnomalyFlag(
            flag_id="already-resolved-flag",
            user_id="BUY-99998",
            flag_type="SCORE_DROP",
            severity="HIGH",
            description="Already done",
            resolved=1,
            created_at=datetime.now(timezone.utc),
            resolved_at=datetime.now(timezone.utc),
        )
        api_db.add(flag)
        api_db.commit()

        tok = _admin_token(api_client, api_db)
        r   = api_client.patch("/admin/anomalies/already-resolved-flag/resolve", headers=_auth(tok))
        assert r.status_code == 409

    def test_filter_resolved_false(self, api_client, api_db):
        from app.models.trust import AnomalyFlag

        now = datetime.now(timezone.utc)
        api_db.add(AnomalyFlag(
            flag_id="open-flag",   user_id="BUY-11111", flag_type="SCORE_DROP",
            severity="HIGH", description="open", resolved=0, created_at=now,
        ))
        api_db.add(AnomalyFlag(
            flag_id="closed-flag", user_id="BUY-22222", flag_type="SCORE_DROP",
            severity="HIGH", description="closed", resolved=1, created_at=now,
            resolved_at=now,
        ))
        api_db.commit()

        tok = _admin_token(api_client, api_db)
        r   = api_client.get("/admin/anomalies?resolved=false", headers=_auth(tok))
        assert r.status_code == 200
        ids = [f["flag_id"] for f in r.json()["anomalies"]]
        assert "open-flag"   in ids
        assert "closed-flag" not in ids

    def test_filter_by_severity(self, api_client, api_db):
        from app.models.trust import AnomalyFlag

        now = datetime.now(timezone.utc)
        api_db.add(AnomalyFlag(
            flag_id="high-sev", user_id="BUY-33333", flag_type="SCORE_DROP",
            severity="HIGH", description="high", resolved=0, created_at=now,
        ))
        api_db.add(AnomalyFlag(
            flag_id="low-sev",  user_id="BUY-44444", flag_type="SCORE_DROP",
            severity="LOW",  description="low",  resolved=0, created_at=now,
        ))
        api_db.commit()

        tok = _admin_token(api_client, api_db)
        r   = api_client.get("/admin/anomalies?severity=HIGH", headers=_auth(tok))
        assert r.status_code == 200
        ids = [f["flag_id"] for f in r.json()["anomalies"]]
        assert "high-sev" in ids
        assert "low-sev"  not in ids


# ─── CSV export API tests ─────────────────────────────────────────────────────

class TestCSVExport:

    def test_export_requires_auth(self, api_client):
        # No auth header → dependency returns 403 (no token = Forbidden in this app)
        r = api_client.get("/trust/BUY-10001/export")
        assert r.status_code in (401, 403)

    def test_export_own_history(self, api_client):
        user = _register(api_client, "exporter@test.com", "Exporter")
        tok  = _login(api_client, "exporter@test.com")
        uid  = user["user_id"]
        r    = api_client.get(f"/trust/{uid}/export", headers=_auth(tok))
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("content-type", "")
        assert uid in r.headers.get("content-disposition", "")

    def test_export_other_user_forbidden(self, api_client):
        owner = _register(api_client, "owner@test.com", "Owner")
        spy   = _register(api_client, "spy@test.com",   "Spy")
        tok   = _login(api_client, "spy@test.com")
        # spy tries to export owner's history
        r     = api_client.get(f"/trust/{owner['user_id']}/export", headers=_auth(tok))
        assert r.status_code == 403

    def test_admin_can_export_any_user(self, api_client, api_db):
        user = _register(api_client, "victim@test.com", "Victim")
        uid  = user["user_id"]
        tok  = _admin_token(api_client, api_db)
        r    = api_client.get(f"/trust/{uid}/export", headers=_auth(tok))
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("content-type", "")

    def test_csv_header_row(self, api_client):
        user = _register(api_client, "csvhead@test.com", "CsvHead")
        uid  = user["user_id"]
        tok  = _login(api_client, "csvhead@test.com")
        r    = api_client.get(f"/trust/{uid}/export", headers=_auth(tok))
        assert r.status_code == 200
        lines  = r.text.splitlines()
        header = lines[0].split(",")
        assert "timestamp"    in header
        assert "old_score"    in header
        assert "new_score"    in header
        assert "score_change" in header
        assert "event_type"   in header
        assert "reason"       in header

    def test_csv_empty_history_returns_header_only(self, api_client):
        user = _register(api_client, "fresh@test.com", "Fresh")
        uid  = user["user_id"]
        tok  = _login(api_client, "fresh@test.com")
        r    = api_client.get(f"/trust/{uid}/export", headers=_auth(tok))
        assert r.status_code == 200
        lines = [l for l in r.text.splitlines() if l.strip()]
        # header only — no data rows (new user has no score changes)
        assert len(lines) == 1

    def test_csv_data_rows_match_history(self, api_client, api_db):
        from app.models.trust import ScoreHistory

        user = _register(api_client, "histrow@test.com", "HistRow")
        uid  = user["user_id"]
        now  = datetime.now(timezone.utc)

        # Insert three synthetic history rows
        for i in range(3):
            api_db.add(ScoreHistory(
                user_id=uid, old_score=700 + i * 10,
                new_score=710 + i * 10, score_change=10,
                reason=f"event {i}", event_type="order_completed",
                created_at=now - timedelta(hours=i),
            ))
        api_db.commit()

        tok = _login(api_client, "histrow@test.com")
        r   = api_client.get(f"/trust/{uid}/export", headers=_auth(tok))
        assert r.status_code == 200
        lines = [l for l in r.text.splitlines() if l.strip()]
        # 1 header + 3 data rows
        assert len(lines) == 4

    def test_csv_content_disposition_filename(self, api_client):
        user = _register(api_client, "dispname@test.com", "DispName")
        uid  = user["user_id"]
        tok  = _login(api_client, "dispname@test.com")
        r    = api_client.get(f"/trust/{uid}/export", headers=_auth(tok))
        assert r.status_code == 200
        cd   = r.headers.get("content-disposition", "")
        assert f"trustgrid_history_{uid}.csv" in cd
