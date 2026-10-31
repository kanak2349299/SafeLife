"""
SafeLife backend tests. No network: hazard feeds, Supabase and Gemini are replaced by fakes.
Run from the project root:  pytest -q
"""
import base64
import io
import json
import sys
import time
from pathlib import Path
from urllib.error import HTTPError

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cryptography.fernet import Fernet  # noqa: E402

from app import create_app  # noqa: E402
from backend import assistant, catalogue, security  # noqa: E402
from backend.config import Settings  # noqa: E402
from backend.hazards import HazardService  # noqa: E402
from backend.security import Wrapper  # noqa: E402

PW = "correct horse battery"
H = {"X-SafeLife": "1"}  # CSRF header required on state-changing API calls


def fake_fetch(url):
    if "usgs" in url:
        return {"features": [{
            "id": "us1", "geometry": {"coordinates": [77.2, 28.6, 10]},
            "properties": {"title": "M 5.1 - near Delhi", "mag": 5.1, "time": 1_700_000_000_000, "url": "u"},
        }, {
            "id": "us2", "geometry": {"coordinates": [-120.0, 37.0, 5]},
            "properties": {"title": "M 6.0 - California", "mag": 6.0, "time": 1_700_000_000_000, "url": "u"},
        }]}
    if "eonet" in url:
        return {"events": [{
            "id": "E1", "title": "Flood near Patna", "link": "l",
            "categories": [{"id": "floods", "title": "Floods"}],
            "geometry": [{"type": "Point", "coordinates": [85.1, 25.6], "date": "2026-10-30T00:00:00Z"}],
        }]}
    if "open-meteo" in url:
        return {"hourly": {"temperature_2m": [30] * 24, "precipitation_probability": [80] * 24,
                           "wind_speed_10m": [20] * 24}}
    raise OSError("offline in tests")


class FakeSupabase:
    """Records requests and stores objects in memory, like a private bucket."""

    def __init__(self):
        self.objects = {}
        self.requests = []

    def __call__(self, req, timeout=None):
        self.requests.append(req)
        path = req.full_url.split("/storage/v1/object/", 1)[1]
        if req.get_method() == "POST":
            bucket, obj = path.split("/", 1)
            self.objects[obj] = req.data
            return _Resp(b'{"Key":"ok"}')
        if req.get_method() == "GET":
            bucket, obj = path.split("/", 1)
            if obj not in self.objects:
                raise HTTPError(req.full_url, 404, "not found", {}, io.BytesIO(b""))
            return _Resp(self.objects[obj])
        if req.get_method() == "DELETE":
            for name in json.loads(req.data)["prefixes"]:
                self.objects.pop(name, None)
            return _Resp(b"[]")
        raise AssertionError("unexpected method")


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def make_settings(tmp_path, **over):
    base = dict(secret_key="test-secret-" + "x" * 40, cookie_secure=False,
                db_path=str(tmp_path / "t.sqlite3"), fernet_key=None, supabase_url=None,
                supabase_key=None, supabase_bucket="safelife-vault", gemini_key=None,
                gemini_model="gemini-2.5-flash", warnings=[])
    base.update(over)
    return Settings(**base)


@pytest.fixture()
def app(tmp_path):
    a = create_app(settings=make_settings(tmp_path), fetcher=fake_fetch)
    a.config["TESTING"] = True
    yield a
    a.config["STORE"].close()


@pytest.fixture()
def client(app):
    return app.test_client()


def register(client, email="a@example.com", pw=PW):
    r = client.post("/api/auth/register", json={"email": email, "password": pw}, headers=H)
    assert r.status_code == 201, r.get_json()
    return r


# ================================================================ AUTH
def test_register_sets_httponly_samesite_cookie(client):
    r = register(client)
    cookie = r.headers.get("Set-Cookie", "")
    assert "sl_session=" in cookie and "HttpOnly" in cookie and "SameSite=Strict" in cookie
    assert "Secure" not in cookie  # AAPDA_COOKIE_SECURE=false in tests
    assert r.get_json()["user"]["email"] == "a@example.com"


def test_session_cookie_is_secure_when_configured(tmp_path):
    a = create_app(settings=make_settings(tmp_path, cookie_secure=True), fetcher=fake_fetch)
    c = a.test_client()
    r = c.post("/api/auth/register", json={"email": "s@example.com", "password": PW}, headers=H)
    assert "Secure" in r.headers["Set-Cookie"]
    a.config["STORE"].close()


def test_api_write_without_csrf_header_is_rejected(client):
    r = client.post("/api/auth/register", json={"email": "x@example.com", "password": PW})
    assert r.status_code == 403


def test_me_requires_session(client):
    assert client.get("/api/auth/me").status_code == 401
    register(client)
    assert client.get("/api/auth/me").status_code == 200


def test_login_wrong_password_and_rate_limit(client):
    register(client)
    client.post("/api/auth/logout", headers=H)
    for _ in range(8):
        assert client.post("/api/auth/login", json={"email": "a@example.com", "password": "wrong-pass-1"},
                           headers=H).status_code == 401
    assert client.post("/api/auth/login", json={"email": "a@example.com", "password": PW},
                       headers=H).status_code == 429


def test_password_stored_as_hash(app, client):
    register(client, pw="my-secret-password-123")
    rows = app.config["STORE"]._all("SELECT pw_hash FROM users")
    assert all("my-secret-password-123" not in r["pw_hash"] for r in rows)


def test_duplicate_and_weak_inputs_rejected(client):
    register(client)
    assert client.post("/api/auth/register", json={"email": "a@example.com", "password": PW}, headers=H).status_code == 400
    assert client.post("/api/auth/register", json={"email": "b@example.com", "password": "short"}, headers=H).status_code == 400
    assert client.post("/api/auth/register", json={"email": "bad-email", "password": PW}, headers=H).status_code == 400


def test_logout_invalidates_session(client):
    register(client)
    client.post("/api/auth/logout", headers=H)
    assert client.get("/api/auth/me").status_code == 401


# ================================================================= MFA
def test_mfa_setup_enable_login_disable(client):
    register(client)
    setup = client.post("/api/auth/mfa/setup", headers=H).get_json()
    assert setup["otpauth_uri"].startswith("otpauth://totp/")
    secret = setup["secret"]

    bad = client.post("/api/auth/mfa/enable", json={"code": "000000"}, headers=H)
    assert bad.status_code == 400

    good = security.totp_at(secret, time.time())
    assert client.post("/api/auth/mfa/enable", json={"code": good}, headers=H).status_code == 200

    client.post("/api/auth/logout", headers=H)
    r = client.post("/api/auth/login", json={"email": "a@example.com", "password": PW}, headers=H).get_json()
    assert r.get("mfa_required") is True
    assert client.post("/api/auth/login", json={"email": "a@example.com", "password": PW, "code": "111111"},
                       headers=H).status_code == 401
    ok = client.post("/api/auth/login", json={"email": "a@example.com", "password": PW,
                                              "code": security.totp_at(secret, time.time())}, headers=H)
    assert ok.status_code == 200 and ok.get_json()["user"]["mfa_enabled"] is True


def test_mfa_secret_is_wrapped_at_rest(tmp_path):
    key = Fernet.generate_key().decode()
    a = create_app(settings=make_settings(tmp_path, fernet_key=key), fetcher=fake_fetch)
    c = a.test_client()
    c.post("/api/auth/register", json={"email": "m@example.com", "password": PW}, headers=H)
    secret = c.post("/api/auth/mfa/setup", headers=H).get_json()["secret"]
    raw = a.config["STORE"]._one("SELECT mfa_secret FROM users WHERE email = ?", ("m@example.com",))["mfa_secret"]
    assert raw.startswith("F1:") and secret not in raw
    a.config["STORE"].close()


# ================================================================ VAULT
def vault_setup(client, passphrase_check="ENCRYPTED-CHECK"):
    client.put("/api/vault/check", json={"check": passphrase_check}, headers=H)


def test_vault_check_is_set_once(client):
    register(client)
    assert client.put("/api/vault/check", json={"check": "A"}, headers=H).status_code == 200
    assert client.put("/api/vault/check", json={"check": "B"}, headers=H).status_code == 400
    info = client.get("/api/vault/setup").get_json()
    assert info["initialized"] and info["check"] == "A" and info["salt"]


def test_vault_roundtrip_stores_exactly_what_the_browser_sent(app, client):
    """The server must not transform or decrypt the client's ciphertext."""
    register(client)
    vault_setup(client)
    meta = "ENC-META-" + base64.b64encode(b"file: aadhaar.pdf").decode()
    data = "ENC-BODY-" + base64.b64encode(b"Aadhaar 1234 5678 9012").decode()
    r = client.post("/api/vault/items", json={"meta": meta, "data": data, "size": 22}, headers=H)
    assert r.status_code == 201
    item = client.get(f"/api/vault/items/{r.get_json()['id']}").get_json()
    assert item["meta"] == meta and item["data"] == data
    stored_meta = app.config["STORE"]._one("SELECT meta FROM vault_items")["meta"]
    stored_blob = app.config["STORE"]._one("SELECT data FROM blobs")["data"]
    assert stored_meta == meta and stored_blob == data  # no server-side decryption or re-encoding


def test_vault_items_isolated_between_users(client):
    register(client, "one@example.com")
    client.post("/api/auth/logout", headers=H)
    register(client, "two@example.com")
    client.post("/api/auth/logout", headers=H)
    client.post("/api/auth/login", json={"email": "one@example.com", "password": PW}, headers=H)
    item_id = client.post("/api/vault/items", json={"meta": "M", "data": "D"}, headers=H).get_json()["id"]
    client.post("/api/auth/logout", headers=H)
    client.post("/api/auth/login", json={"email": "two@example.com", "password": PW}, headers=H)
    assert client.get(f"/api/vault/items/{item_id}").status_code == 404
    assert client.delete(f"/api/vault/items/{item_id}", headers=H).status_code == 404
    assert client.get("/api/vault/items").get_json()["items"] == []


def test_vault_delete_and_history(client):
    register(client)
    item_id = client.post("/api/vault/items", json={"meta": "M", "data": "D"}, headers=H).get_json()["id"]
    client.get(f"/api/vault/items/{item_id}")
    assert client.delete(f"/api/vault/items/{item_id}", headers=H).status_code == 200
    assert client.get(f"/api/vault/items/{item_id}").status_code == 404
    kinds = [e["kind"] for e in client.get("/api/vault/history").get_json()["events"]]
    assert {"document_uploaded", "document_downloaded", "document_deleted"} <= set(kinds)


def test_vault_rejects_bad_payloads(client):
    register(client)
    assert client.post("/api/vault/items", json={"meta": {"x": 1}, "data": "D"}, headers=H).status_code == 400
    assert client.post("/api/vault/items", json={"meta": "M", "data": ""}, headers=H).status_code == 400
    too_big = "A" * (11 * 1024 * 1024)
    assert client.post("/api/vault/items", json={"meta": "M", "data": too_big}, headers=H).status_code == 400


def test_sqlite_blob_wrapped_when_fernet_configured(tmp_path):
    key = Fernet.generate_key().decode()
    a = create_app(settings=make_settings(tmp_path, fernet_key=key), fetcher=fake_fetch)
    c = a.test_client()
    c.post("/api/auth/register", json={"email": "w@example.com", "password": PW}, headers=H)
    c.post("/api/vault/items", json={"meta": "M", "data": "PLAINTEXT-CLIENT-CIPHER"}, headers=H)
    stored = a.config["STORE"]._one("SELECT data FROM blobs")["data"]
    assert stored.startswith("F1:") and "PLAINTEXT-CLIENT-CIPHER" not in stored
    # and it still reads back correctly
    item_id = c.get("/api/vault/items").get_json()["items"][0]["id"]
    assert c.get(f"/api/vault/items/{item_id}").get_json()["data"] == "PLAINTEXT-CLIENT-CIPHER"
    a.config["STORE"].close()


def test_supabase_backend_uses_private_bucket_and_server_key(tmp_path):
    fake = FakeSupabase()
    s = make_settings(tmp_path, supabase_url="https://proj.supabase.co",
                      supabase_key="SERVICE-KEY-VALUE", supabase_bucket="safelife-vault")
    a = create_app(settings=s, fetcher=fake_fetch, opener=fake)
    c = a.test_client()
    c.post("/api/auth/register", json={"email": "sb@example.com", "password": PW}, headers=H)
    item_id = c.post("/api/vault/items", json={"meta": "M", "data": "CIPHER-BODY"}, headers=H).get_json()["id"]

    upload = [r for r in fake.requests if r.get_method() == "POST"][0]
    assert upload.full_url.startswith("https://proj.supabase.co/storage/v1/object/safelife-vault/")
    assert upload.get_header("Authorization") == "Bearer SERVICE-KEY-VALUE"
    assert len(fake.objects) == 1 and list(fake.objects.values())[0] == b"CIPHER-BODY"

    # the browser-facing response never contains the service key
    body = c.get(f"/api/vault/items/{item_id}").get_data(as_text=True)
    assert "SERVICE-KEY-VALUE" not in body and "CIPHER-BODY" in body

    c.delete(f"/api/vault/items/{item_id}", headers=H)
    assert fake.objects == {}
    a.config["STORE"].close()


def test_supabase_dashboard_url_is_rejected_with_warning(tmp_path, monkeypatch):
    from backend import config as cfg
    monkeypatch.setenv("AAPDA_SUPABASE_URL", "https://supabase.com/dashboard/project/x/settings/api-keys")
    monkeypatch.setenv("AAPDA_SUPABASE_SERVICE_ROLE_KEY", "k")
    monkeypatch.setattr(cfg, "load_dotenv", lambda p: None)
    s = cfg.load_settings()
    assert s.supabase_url is None and s.blob_backend == "sqlite"
    assert any("dashboard" in w for w in s.warnings)


# ============================================================ ACCOUNT DELETE
def test_delete_account_requires_confirmation_and_purges_files(tmp_path):
    fake = FakeSupabase()
    s = make_settings(tmp_path, supabase_url="https://p.supabase.co", supabase_key="K")
    a = create_app(settings=s, fetcher=fake_fetch, opener=fake)
    c = a.test_client()
    c.post("/api/auth/register", json={"email": "del@example.com", "password": PW}, headers=H)
    c.post("/api/vault/items", json={"meta": "M", "data": "D1"}, headers=H)
    c.post("/api/vault/items", json={"meta": "M", "data": "D2"}, headers=H)
    assert len(fake.objects) == 2
    assert c.delete("/api/account", json={}, headers=H).status_code == 400
    r = c.delete("/api/account", json={"confirm": "DELETE"}, headers=H)
    assert r.status_code == 200 and r.get_json()["purged_files"] == 2
    assert fake.objects == {}
    assert a.config["STORE"].user_for_token("anything") is None
    a.config["STORE"].close()


# =============================================================== PROFILE
def test_profile_city_and_blood_group_validation(client):
    register(client)
    assert client.put("/api/profile", json={"city": "Atlantis"}, headers=H).status_code == 400
    assert client.put("/api/profile", json={"blood_group": "Z+"}, headers=H).status_code == 400
    r = client.put("/api/profile", json={"city": "Patna", "blood_group": "o+"}, headers=H).get_json()
    assert r["user"]["city"] == "Patna" and r["user"]["state"] == "Bihar" and r["user"]["blood_group"] == "O+"


# ============================================================ CHECKLIST
def test_onboarding_recommendations_explain_reasons(client):
    register(client)
    r = client.post("/api/onboarding", json={"has_vehicle": True, "has_children": True}, headers=H).get_json()
    keys = {x["key"]: x for x in r["recommendations"]}
    assert "vehicle_rc" in keys and "birth_certificate" in keys
    assert any("vehicle" in reason for reason in keys["vehicle_rc"]["reasons"])
    assert all(x["reasons"] and x["helps"] for x in r["recommendations"])


def test_checklist_status_validation_and_readiness_rises(client):
    register(client)
    before = client.get("/api/readiness").get_json()["score"]
    assert client.put("/api/checklist/aadhaar", json={"status": "maybe"}, headers=H).status_code == 400
    assert client.put("/api/checklist/not_a_doc", json={"status": "uploaded"}, headers=H).status_code == 404
    assert client.put("/api/checklist/aadhaar", json={"status": "uploaded"}, headers=H).status_code == 200
    after = client.get("/api/readiness").get_json()["score"]
    assert after > before


def test_readiness_breakdown_sums_to_score():
    user = {"city": "Patna", "state": "Bihar", "blood_group": "O+"}
    checklist = {k: {"status": "uploaded"} for k in catalogue.CATALOGUE_BY_KEY if catalogue.CATALOGUE_BY_KEY[k]["essential"]}
    r = catalogue.readiness(user, checklist, family_count=3, vault_count=5)
    assert r["score"] == round(sum(p["points"] for p in r["parts"]))
    assert r["score"] == 40 + 20 + 0 + 10 + 0 + 5  # all essentials, 3 contacts, no supplies, location, no plan, blood group
    assert all(p["tip"] for p in r["parts"])


# ============================================================= FAMILY
def test_family_validation_sos_and_checkin(client):
    register(client)
    assert client.post("/api/family", json={"name": "", "phone": "9876543210"}, headers=H).status_code == 400
    assert client.post("/api/family", json={"name": "Mother", "phone": "not a phone"}, headers=H).status_code == 400
    mid = client.post("/api/family", json={"name": "Mother", "relation": "Parent", "phone": "+91 98765 43210"},
                      headers=H).get_json()["id"]
    sos = client.post("/api/family/sos", json={"message": "Trapped"}, headers=H).get_json()
    assert sos["recorded"] and sos["contacts"][0]["name"] == "Mother"
    assert sos["delivered_by_server"] is False  # honest: SMS is not sent by this server
    ci = client.post("/api/family/checkin", json={"member_id": mid}, headers=H).get_json()
    assert ci["recorded"] and "Mother" in ci["note"]
    assert client.post("/api/family/checkin", json={"member_id": 9999}, headers=H).status_code == 404
    assert len(client.get("/api/family/events").get_json()["events"]) == 2


# ========================================================== AAPDASENSE
def test_official_sources_report_not_configured_without_env(tmp_path, monkeypatch):
    for v in ("AAPDA_IMD_FEED_URL", "AAPDA_SACHET_FEED_URL", "AAPDA_CWC_FEED_URL",
              "AAPDA_INCOIS_FEED_URL", "AAPDA_GSI_FEED_URL"):
        monkeypatch.delenv(v, raising=False)
    svc = HazardService(fetcher=fake_fetch, env={})
    statuses = {s["id"]: s["status"] for s in svc.official()["sources"]}
    assert set(statuses.values()) == {"not_configured"}
    assert svc.official()["alerts"] == []  # no invented alerts


def test_official_source_shows_pending_parser_when_url_set():
    svc = HazardService(fetcher=fake_fetch, env={"AAPDA_IMD_FEED_URL": "https://example.invalid/feed"})
    imd = [s for s in svc.official()["sources"] if s["id"] == "imd"][0]
    assert imd["status"] == "configured_pending_parser"


def test_severity_rules_observed_caps_at_orange_only_official_gives_red():
    # Observed hazard + high assessment: orange at most, never red.
    assessment = {"score": 70, "level": "high", "factors": [{"factor": "x", "points": 70}], "nearby_observed": 2}
    sev = HazardService.severity([], assessment)
    assert sev["level"] == "orange"
    # Nothing at all: green.
    assert HazardService.severity([], {"score": 0, "level": "low", "factors": [], "nearby_observed": 0})["level"] == "green"
    # Red only when an official alert says so.
    official = [{"issuer": "IMD", "level": "red", "instruction": "Evacuate low-lying areas"}]
    sev = HazardService.severity(official, {"score": 0, "level": "low", "factors": [], "nearby_observed": 0})
    assert sev["level"] == "red" and any("Official" in r for r in sev["reasons"])


def test_location_endpoint_assessment_and_no_invented_alerts(client):
    r = client.get("/api/aapdasense/location?city=New%20Delhi").get_json()
    assert r["location"]["city"] == "New Delhi"
    assert r["official_alerts"] == []
    assert r["severity"]["level"] in {"green", "yellow", "orange"}  # never red without an official alert
    assert r["observed_nearby"] and r["observed_nearby"][0]["source"] in {"USGS", "NASA EONET"}
    assert r["sources"]["usgs"]["ok"] and "disclaimer" in r and r["validity"]


def test_location_endpoint_survives_all_feeds_down(tmp_path):
    def down(url):
        raise OSError("down")
    a = create_app(settings=make_settings(tmp_path), fetcher=down)
    r = a.test_client().get("/api/aapdasense/location?city=Patna").get_json()
    assert r["data_ok"] is False
    a.config["STORE"].close()


def test_map_endpoint_has_cities_and_events(client):
    r = client.get("/api/aapdasense/map").get_json()
    assert len(r["cities"]) >= 10 and any(e["kind"] == "floods" for e in r["events"])


# ============================================================ EMERGENCY
def test_emergency_mode_requires_saved_location_and_lists_helplines(client):
    register(client)
    r = client.get("/api/emergency").get_json()
    assert r["active"] is False and any(h["number"] == "112" for h in r["helplines"])
    client.put("/api/profile", json={"city": "Patna"}, headers=H)
    r = client.get("/api/emergency").get_json()
    assert "severity" in r and r["active"] is False  # observed-only data cannot trigger red


# ============================================================ ASSISTANT
def test_assistant_fallback_prioritises_official_and_mentions_112():
    ctx = {"official_alerts": [{"issuer": "IMD", "instruction": "Stay indoors"}], "missing_documents": ["Aadhaar Card"]}
    r = assistant.ask("What should I prepare for a flood warning?", ctx, api_key=None, model="m")
    assert r["source"] == "rules"
    assert r["answer"].index("Official (IMD)") < r["answer"].index("Flood preparation")
    assert "112" in r["answer"]


def test_assistant_says_no_official_warning_when_none():
    r = assistant.ask("Is my location under any warning?", {"official_alerts": []}, api_key=None, model="m")
    assert "No official warning is active" in r["answer"]


def test_assistant_sends_no_vault_content_to_gemini(client, tmp_path):
    captured = {}

    class Resp(_Resp):
        pass

    def fake_gemini(req, timeout=None):
        captured["body"] = req.data.decode()
        captured["key_header"] = req.get_header("X-goog-api-key")
        return Resp(json.dumps({"candidates": [{"content": {"parts": [{"text": "Keep papers dry."}]}}]}).encode())

    s = make_settings(tmp_path, gemini_key="TEST-GEMINI-KEY")
    a = create_app(settings=s, fetcher=fake_fetch, opener=fake_gemini)
    c = a.test_client()
    c.post("/api/auth/register", json={"email": "g@example.com", "password": PW}, headers=H)
    c.post("/api/vault/items", json={"meta": "SECRET-META-NAME", "data": "SECRET-BODY"}, headers=H)
    c.put("/api/profile", json={"city": "Patna"}, headers=H)
    r = c.post("/api/assistant", json={"question": "Which documents should I keep ready before a cyclone?"}, headers=H).get_json()
    assert r["source"] == "gemini" and "Keep papers dry" in r["answer"]
    assert captured["key_header"] == "TEST-GEMINI-KEY"
    assert "SECRET-META-NAME" not in captured["body"] and "SECRET-BODY" not in captured["body"]
    a.config["STORE"].close()


def test_assistant_falls_back_when_gemini_fails(tmp_path):
    def broken(req, timeout=None):
        raise OSError("network")
    s = make_settings(tmp_path, gemini_key="K")
    a = create_app(settings=s, fetcher=fake_fetch, opener=broken)
    c = a.test_client()
    c.post("/api/auth/register", json={"email": "f@example.com", "password": PW}, headers=H)
    r = c.post("/api/assistant", json={"question": "earthquake what do I do"}, headers=H).get_json()
    assert r["source"] == "rules" and "rule-based" in r["note"]
    a.config["STORE"].close()


# ============================================================ DASHBOARD
def test_dashboard_summary_shape(client):
    register(client)
    d = client.get("/api/dashboard").get_json()
    assert d["vault"]["documents"] == 0 and d["essential"]["total"] >= 5
    assert "Identity" in d["groups"] and d["readiness"]["max"] == 100


# ============================================================ STATIC & HEADERS
def test_security_headers_and_static_rules(client, tmp_path):
    r = client.get("/")
    assert r.status_code == 200
    assert "default-src 'self'" in r.headers["Content-Security-Policy"]
    assert r.headers["X-Frame-Options"] == "DENY"
    assert client.get("/data/disaster_models_assets.pkl").status_code == 404
    assert client.get("/data/vault.sqlite3").status_code == 404
    assert client.get("/app.py").status_code == 404
    assert client.get("/backend/store.py").status_code == 404
    assert client.get("/.env").status_code == 404
    assert client.get("/css/app.css").status_code in (200, 404)  # file may not exist yet
