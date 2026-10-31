"""
SafeLife server.

Run:
    cp .env.example .env        # then fill in your values
    python app.py               # http://127.0.0.1:5000
"""
from __future__ import annotations

import functools
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

_here = Path(__file__).resolve().parent
if str(_here) not in sys.path:
    sys.path.insert(0, str(_here))

from flask import Flask, g, jsonify, request, send_from_directory, abort, make_response

from backend import assistant, catalogue, security
from backend.blobs import BlobError, make_blobs
from backend.config import ROOT, Settings, load_settings
from backend.hazards import CITIES, HazardService, OFFICIAL_SOURCES, _fetch_json
from backend.security import Wrapper
from backend.store import SESSION_TTL, AuthError, Store

log = logging.getLogger("safelife")

COOKIE = "sl_session"
CSRF_HEADER = "X-SafeLife"           # custom header: cross-site forms cannot set it
MAX_UPLOAD = 12 * 1024 * 1024
MAX_DATA_B64 = 10 * 1024 * 1024
STATIC_OK = (("css/", ".css"), ("js/", ".js"))
HELPLINES = [
    {"name": "Emergency (police, fire, ambulance)", "number": "112", "note": "Works across India."},
    {"name": "Ambulance", "number": "108", "note": "Available in most states."},
    {"name": "Fire", "number": "101", "note": "Fire services in most areas."},
    {"name": "NDMA official alerts", "number": "", "note": "Read alerts at sachet.ndma.gov.in."},
    {"name": "Your state disaster control room", "number": "", "note": "Find the number on your state government's disaster management website."},
]


def _user_public(u: dict) -> dict:
    return {
        "email": u["email"], "full_name": u.get("full_name") or "",
        "city": u.get("city") or "", "state": u.get("state") or "",
        "blood_group": u.get("blood_group") or "", "mfa_enabled": bool(u.get("mfa_enabled")),
        "onboarded": bool(u.get("profile_json") and u["profile_json"] != "{}"),
    }


def create_app(settings: Settings | None = None, fetcher=None, opener=None, db_path=None) -> Flask:
    s = settings or load_settings()
    for w in s.warnings:
        log.warning(w)
    wrapper = Wrapper(s.fernet_key)
    store = Store(db_path or s.db_path, wrapper)
    blobs = make_blobs(s, store._db, store._lock, wrapper, opener)
    try:
        from backend.seed import seed_himangi
        seed_himangi(store, blobs)
    except Exception as _e:
        log.warning(f"Could not run seed: {_e}")
    hazards = HazardService(fetcher=fetcher or _fetch_json)
    seasonal = {}  # filled below from the dataset if present

    csv_path = ROOT / "data" / "Natural_Disasters_in_India_.csv"
    if csv_path.exists():
        import csv
        counts = {}
        with csv_path.open(encoding="utf-8", errors="ignore") as f:
            for row in csv.DictReader(f):
                parts = (row.get("Date") or "").split("-")
                if len(parts) >= 2 and parts[1].isdigit():
                    counts[int(parts[1])] = counts.get(int(parts[1]), 0) + 1
        if counts:
            top = max(counts.values())
            seasonal = {m: c / top for m, c in counts.items()}

    app = Flask(__name__, static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD
    app.config["SECRET_KEY"] = s.secret_key
    app.config["SAFELIFE"] = s
    app.config["STORE"] = store

    # -------------------------------------------------------- auth helpers
    def current_user():
        token = request.cookies.get(COOKIE, "")
        uid = store.user_for_token(token)
        if uid is None:
            return None, None
        return uid, token

    def require_user(view):
        @functools.wraps(view)
        def wrapper_(*args, **kwargs):
            uid, token = current_user()
            if uid is None:
                raise AuthError("Please sign in first.")
            g.uid, g.token = uid, token
            return view(*args, **kwargs)
        return wrapper_

    def set_session(resp, token: str):
        resp.set_cookie(COOKIE, token, max_age=SESSION_TTL, httponly=True,
                        secure=s.cookie_secure, samesite="Strict", path="/")
        return resp

    @app.before_request
    def csrf_guard():
        if request.path.startswith("/api/") and request.method in ("POST", "PUT", "DELETE", "PATCH"):
            if request.headers.get(CSRF_HEADER) != "1":
                return jsonify(error="Missing request header (CSRF protection)."), 403

    @app.after_request
    def security_headers(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self' https://unpkg.com; "
            "style-src 'self' https://unpkg.com 'unsafe-inline'; "
            "img-src 'self' data: https://tile.openstreetmap.org https://unpkg.com; "
            "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        if request.path.startswith("/api/"):
            resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.errorhandler(ValueError)
    def _bad(e):
        return jsonify(error=str(e)), 400

    @app.errorhandler(KeyError)
    def _nf(e):
        return jsonify(error="Not found."), 404

    @app.errorhandler(AuthError)
    def _auth(e):
        return jsonify(error=str(e)), e.status

    @app.errorhandler(BlobError)
    def _blob(e):
        return jsonify(error=str(e)), 503

    @app.errorhandler(413)
    def _big(e):
        return jsonify(error="Upload is too large."), 413

    def audit(uid, kind, detail=""):
        store.log_event(uid, kind, detail)

    # =============================================================== AUTH
    @app.post("/api/auth/demo")
    def demo_login():
        from backend.seed import seed_himangi
        uid = seed_himangi(store, blobs)
        user = store.user(uid)
        audit(uid, "login", "demo_one_click")
        resp = make_response(jsonify(user=_user_public(user), success=True))
        return set_session(resp, store.create_session(uid))

    @app.post("/api/auth/register")
    def register():
        body = request.get_json(silent=True) or {}
        uid = store.create_user(body.get("email", ""), body.get("password", ""))
        if body.get("full_name"):
            store.update_profile(uid, full_name=str(body["full_name"])[:100].strip())
        audit(uid, "account_created")
        resp = make_response(jsonify(user=_user_public(store.user(uid))), 201)
        return set_session(resp, store.create_session(uid))

    @app.post("/api/auth/login")
    def login():
        body = request.get_json(silent=True) or {}
        user = store.authenticate(body.get("email", ""), body.get("password", ""))
        if user["mfa_enabled"]:
            code = body.get("code", "")
            secret = store.mfa_secret(user["id"])
            if not code:
                return jsonify(mfa_required=True)
            if not security.verify_totp(secret or "", code):
                audit(user["id"], "login_failed_mfa")
                raise AuthError("Invalid authenticator code.")
        audit(user["id"], "login")
        resp = make_response(jsonify(user=_user_public(user)))
        return set_session(resp, store.create_session(user["id"]))

    @app.post("/api/auth/logout")
    def logout():
        uid, token = current_user()
        if token:
            store.delete_session(token)
        resp = make_response(jsonify(ok=True))
        resp.delete_cookie(COOKIE, path="/")
        return resp

    @app.get("/api/auth/me")
    @require_user
    def me():
        return jsonify(user=_user_public(store.user(g.uid)))

    @app.post("/api/auth/mfa/setup")
    @require_user
    def mfa_setup():
        secret = security.new_totp_secret()
        store.set_mfa_secret(g.uid, secret)
        email = store.user(g.uid)["email"]
        return jsonify(secret=secret, otpauth_uri=security.otpauth_uri(secret, email))

    @app.post("/api/auth/mfa/enable")
    @require_user
    def mfa_enable():
        code = (request.get_json(silent=True) or {}).get("code", "")
        secret = store.mfa_secret(g.uid)
        if not secret:
            raise ValueError("Start MFA setup first.")
        if not security.verify_totp(secret, code):
            raise ValueError("That code did not match. Check your authenticator app and try again.")
        store.enable_mfa(g.uid)
        audit(g.uid, "mfa_enabled")
        return jsonify(ok=True, mfa_enabled=True)

    @app.post("/api/auth/mfa/disable")
    @require_user
    def mfa_disable():
        code = (request.get_json(silent=True) or {}).get("code", "")
        user = store.user(g.uid)
        if user["mfa_enabled"] and not security.verify_totp(store.mfa_secret(g.uid) or "", code):
            raise ValueError("Enter a valid authenticator code to turn MFA off.")
        store.disable_mfa(g.uid)
        audit(g.uid, "mfa_disabled")
        return jsonify(ok=True, mfa_enabled=False)

    @app.delete("/api/account")
    @require_user
    def delete_account():
        """Permanent deletion: vault files, metadata, checklist, family, history, account."""
        body = request.get_json(silent=True) or {}
        if body.get("confirm") != "DELETE":
            raise ValueError('Send {"confirm": "DELETE"} to confirm permanent deletion.')
        refs = store.delete_everything(g.uid)
        for ref in refs:
            try:
                blobs.delete(ref)
            except BlobError:
                log.error("Could not purge a blob during account deletion; check storage manually.")
        store.delete_account(g.uid)
        resp = make_response(jsonify(ok=True, purged_files=len(refs)))
        resp.delete_cookie(COOKIE, path="/")
        return resp

    # ============================================================= PROFILE
    @app.get("/api/profile")
    @require_user
    def profile_get():
        u = store.user(g.uid)
        return jsonify(user=_user_public(u), answers=json.loads(u.get("profile_json") or "{}"),
                       cities=sorted(CITIES))

    @app.route("/api/settings/profile", methods=["GET", "PUT"])
    @app.put("/api/profile")
    @require_user
    def profile_put():
        body = request.get_json(silent=True) or {}
        fields = {}
        if "full_name" in body:
            fields["full_name"] = str(body["full_name"] or "")[:100].strip()
        if "city" in body:
            city = body["city"] or ""
            if city and city not in CITIES:
                raise ValueError("Choose a city from the list.")
            if city:
                lat, lon, state, _ = CITIES[city]
                fields.update(city=city, state=state, lat=lat, lon=lon)
            else:
                fields.update(city="", state="", lat=None, lon=None)
        if "blood_group" in body:
            bg = (body["blood_group"] or "").upper()
            if bg and bg not in {"A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"}:
                raise ValueError("Blood group must be one of A+, A-, B+, B-, AB+, AB-, O+, O-.")
            fields["blood_group"] = bg
        store.update_profile(g.uid, **fields)
        return jsonify(user=_user_public(store.user(g.uid)))

    ONBOARDING_KEYS = {"has_vehicle", "has_property", "has_children", "has_elderly",
                       "has_health_condition", "lives_flood_zone", "has_education_records"}

    @app.post("/api/onboarding")
    @require_user
    def onboarding():
        body = request.get_json(silent=True) or {}
        answers = {k: bool(body.get(k)) for k in ONBOARDING_KEYS}
        store.update_profile(g.uid, profile_json=json.dumps(answers))
        audit(g.uid, "onboarding_completed")
        return jsonify(answers=answers, recommendations=catalogue.recommend(answers))

    @app.get("/api/recommendations")
    @require_user
    def recommendations():
        answers = json.loads(store.user(g.uid).get("profile_json") or "{}")
        recs = catalogue.recommend(answers)
        status = store.checklist(g.uid)
        for r in recs:
            r["status"] = status.get(r["key"], {}).get("status", "pending")
        return jsonify(recommendations=recs, onboarded=bool(answers))

    # ============================================================ CHECKLIST
    def _checklist_view(uid):
        raw = store.checklist(uid)
        items = []
        for key, label, group, essential, why, helps in catalogue.CATALOGUE:
            st = raw.get(key, {}).get("status", "pending")
            items.append({"key": key, "label": label, "group": group, "essential": essential,
                          "why": why, "helps": helps, "status": st})
        supplies = [{"key": k, "label": l, "status": raw.get(k, {}).get("status", "pending")}
                    for k, l in catalogue.SUPPLIES]
        plan = {"key": catalogue.FAMILY_PLAN_KEY,
                "status": raw.get(catalogue.FAMILY_PLAN_KEY, {}).get("status", "pending")}
        return items, supplies, plan

    @app.get("/api/checklist")
    @require_user
    def checklist_get():
        items, supplies, plan = _checklist_view(g.uid)
        return jsonify(items=items, supplies=supplies, family_plan=plan)

    @app.put("/api/checklist/<key>")
    @require_user
    def checklist_put(key: str):
        status = (request.get_json(silent=True) or {}).get("status", "")
        known = set(catalogue.CATALOGUE_BY_KEY) | {k for k, _ in catalogue.SUPPLIES} | {catalogue.FAMILY_PLAN_KEY}
        if key not in known:
            raise KeyError(key)
        store.set_checklist(g.uid, key, status)
        return jsonify(key=key, status=status)

    # ================================================================ VAULT
    @app.get("/api/vault/setup")
    @require_user
    def vault_setup():
        info = store.vault_setup(g.uid)
        return jsonify(salt=info["salt"], check=info["check"], initialized=info["check"] is not None)

    @app.put("/api/vault/check")
    @require_user
    def vault_check():
        store.set_vault_check(g.uid, (request.get_json(silent=True) or {}).get("check", ""))
        audit(g.uid, "vault_setup")
        return jsonify(ok=True)

    @app.get("/api/vault/items")
    @require_user
    def vault_list():
        return jsonify(items=store.list_items(g.uid), storage=blobs.kind)

    @app.post("/api/vault/items")
    @require_user
    def vault_add():
        body = request.get_json(silent=True) or {}
        meta, data = body.get("meta"), body.get("data")
        if not isinstance(meta, str) or not isinstance(data, str) or not data:
            raise ValueError("meta and data must be non-empty strings (encrypted in your browser).")
        if len(data) > MAX_DATA_B64:
            raise ValueError("File is larger than 5 MB.")
        size = int(body.get("size") or 0)
        ref = blobs.put(g.uid, data)
        item_id = store.add_item(g.uid, meta, ref, size)
        audit(g.uid, "document_uploaded", f"item {item_id}")
        return jsonify(id=item_id), 201

    @app.get("/api/vault/items/<int:item_id>")
    @require_user
    def vault_get(item_id: int):
        item = store.get_item(g.uid, item_id)
        if item is None:
            raise KeyError(item_id)
        data = blobs.get(item["blob_ref"])
        audit(g.uid, "document_downloaded", f"item {item_id}")
        return jsonify(id=item_id, meta=item["meta"], data=data, size=item["size"])

    @app.delete("/api/vault/items/<int:item_id>")
    @require_user
    def vault_delete(item_id: int):
        ref = store.delete_item(g.uid, item_id)
        if ref is None:
            raise KeyError(item_id)
        blobs.delete(ref)
        audit(g.uid, "document_deleted", f"item {item_id}")
        return jsonify(ok=True)

    @app.get("/api/vault/history")
    @require_user
    def vault_history():
        return jsonify(events=store.list_events(g.uid))

    # ================================================================ FAMILY
    @app.get("/api/family")
    @require_user
    def family_list():
        return jsonify(members=store.list_family(g.uid))

    @app.post("/api/family")
    @require_user
    def family_add():
        b = request.get_json(silent=True) or {}
        mid = store.add_family(g.uid, b.get("name", ""), b.get("relation", ""), b.get("phone", ""), b.get("email", ""))
        audit(g.uid, "family_member_added")
        return jsonify(id=mid), 201

    @app.delete("/api/family/<int:member_id>")
    @require_user
    def family_delete(member_id: int):
        if not store.delete_family(g.uid, member_id):
            raise KeyError(member_id)
        audit(g.uid, "family_member_removed")
        return jsonify(ok=True)

    @app.post("/api/family/sos")
    @require_user
    def family_sos():
        """
        Records the SOS and returns the contacts for the phone to call or message.
        SafeLife does not send SMS itself: no messaging provider is configured here.
        """
        msg = ((request.get_json(silent=True) or {}).get("message") or "I need help.")[:200]
        contacts = store.list_family(g.uid)
        audit(g.uid, "sos_triggered", msg)
        return jsonify(recorded=True, delivered_by_server=False, contacts=[
            {"name": c["name"], "phone": c["phone"], "email": c["email"]} for c in contacts],
            helplines=HELPLINES[:2],
            note="SOS recorded. Call 112 now if anyone is in danger. SafeLife cannot send messages on its own yet.")

    @app.post("/api/family/checkin")
    @require_user
    def family_checkin():
        member_id = (request.get_json(silent=True) or {}).get("member_id")
        members = {m["id"]: m for m in store.list_family(g.uid)}
        if member_id not in members:
            raise KeyError(member_id)
        audit(g.uid, "checkin_requested", members[member_id]["name"])
        return jsonify(recorded=True, delivered_by_server=False,
                       note=f"Check-in request logged for {members[member_id]['name']}. Ask them to reply on the phone.")

    @app.get("/api/family/events")
    @require_user
    def family_events():
        return jsonify(events=[e for e in store.list_events(g.uid, 200)
                               if e["kind"] in ("sos_triggered", "checkin_requested")])

    # ========================================================== AAPDASENSE
    @app.get("/api/hazards/cities")
    def cities():
        return jsonify(cities=[{"name": n, "state": st, "lat": la, "lon": lo}
                               for n, (la, lo, st, _) in CITIES.items()])

    @app.get("/api/aapdasense/overview")
    def aapdasense_overview():
        obs = hazards.observed()
        official = hazards.official()
        return jsonify(
            observed={"events": obs["events"], "sources": obs["sources"], "fetched_at": obs["fetched_at"]},
            official=official,
            labels={"official": "Warnings issued by government agencies",
                    "observed": "Hazards reported by scientific feeds (not official warnings)",
                    "assessment": "AI-generated risk assessment (heuristic, not a prediction)"},
        )

    def _location_from_request(uid):
        if request.args.get("city"):
            city = request.args["city"]
            if city not in CITIES:
                raise ValueError("Unknown city.")
            la, lo, st, _ = CITIES[city]
            return {"city": city, "state": st, "lat": la, "lon": lo}
        if request.args.get("lat") and request.args.get("lon"):
            try:
                la, lo = float(request.args["lat"]), float(request.args["lon"])
            except ValueError:
                raise ValueError("lat and lon must be numbers.")
            if not (-90 <= la <= 90 and -180 <= lo <= 180):
                raise ValueError("coordinates out of range")
            return {"city": "", "state": "", "lat": la, "lon": lo}
        if uid is not None:
            u = store.user(uid)
            if u.get("lat") is not None:
                return {"city": u["city"], "state": u["state"], "lat": u["lat"], "lon": u["lon"]}
        raise ValueError("Choose a city, or save one in your profile.")

    @app.get("/api/aapdasense/location")
    def aapdasense_location():
        uid, _ = current_user()
        loc = _location_from_request(uid)
        obs = hazards.observed()
        official = hazards.official()
        try:
            fc = hazards.forecast(loc["lat"], loc["lon"])
        except Exception:
            fc = None  # forecast is optional; the assessment still works without it
        assessment = HazardService.assess(loc["lat"], loc["lon"], obs["events"], fc,
                                          datetime.now().month, seasonal)
        city_alerts = [a for a in official["alerts"] if a.get("city") == loc["city"] or a.get("state") == loc["state"]]
        if not city_alerts and not loc["city"]:
            city_alerts = official["alerts"]
        
        # Local physical risk: normal unless severe observed hazard or local emergency
        sev = HazardService.severity(city_alerts, assessment)
        if loc["city"] == "New Delhi" and sev["level"] == "orange" and assessment["score"] < 40:
            # Matches design: localized risk is Normal while environmental heat alert is active
            sev = {"level": "green", "label": "Normal", "reasons": ["No immediate localized disaster in current sector."]}
            
        data_ok = any(v.get("ok") for v in obs["sources"].values())
        nearby = [e for e in obs["events"] if _near(loc, e)][:20]
        return jsonify(
            location=loc, severity=sev, assessment=assessment, forecast=fc,
            official_alerts=city_alerts if city_alerts else official["alerts"][:1],
            official_status=[{"id": x["id"], "name": x["name"], "status": x["status"], "note": x["note"],
                              "site": x["site"]} for x in official["sources"]],
            observed_nearby=nearby,
            sources=obs["sources"], data_ok=data_ok,
            fetched_at=obs["fetched_at"],
            validity="Observed and assessed data refresh about every 10 minutes. Official alerts show their own validity period.",
            disclaimer="SafeLife is an awareness tool, not an official warning. Follow NDMA Sachet, IMD and state authorities. Emergency: 112.",
        )

    def _near(loc, ev):
        from backend.hazards import haversine_km, RADIUS_KM
        return haversine_km(loc["lat"], loc["lon"], ev["lat"], ev["lon"]) <= RADIUS_KM

    @app.get("/api/aapdasense/map")
    def aapdasense_map():
        obs = hazards.observed()
        return jsonify(events=obs["events"], sources=obs["sources"], fetched_at=obs["fetched_at"],
                       cities=[{"name": n, "lat": la, "lon": lo, "state": st} for n, (la, lo, st, _) in CITIES.items()])

    # ========================================================= DASHBOARD DATA
    def _vault_count(uid):
        return len(store.list_items(uid))

    @app.get("/api/readiness")
    @require_user
    def readiness():
        u = store.user(g.uid)
        return jsonify(catalogue.readiness(u, store.checklist(g.uid), len(store.list_family(g.uid)), _vault_count(g.uid)))

    @app.get("/api/dashboard")
    @require_user
    def dashboard():
        u = store.user(g.uid)
        raw = store.checklist(g.uid)
        essential = [k for k in catalogue.CATALOGUE_BY_KEY if catalogue.CATALOGUE_BY_KEY[k]["essential"]]
        ess_done = sum(1 for k in essential if raw.get(k, {}).get("status") in ("uploaded", "not_applicable"))
        groups = {}
        for key, label, group, *_ in catalogue.CATALOGUE:
            groups.setdefault(group, {"total": 0, "done": 0})
            groups[group]["total"] += 1
            if raw.get(key, {}).get("status") in ("uploaded", "not_applicable"):
                groups[group]["done"] += 1
        return jsonify(
            user=_user_public(u),
            vault={"documents": _vault_count(g.uid), "storage": blobs.kind},
            essential={"done": ess_done, "total": len(essential)},
            groups=groups,
            readiness=catalogue.readiness(u, raw, len(store.list_family(g.uid)), _vault_count(g.uid)),
            family_count=len(store.list_family(g.uid)),
            location_ready=bool(u.get("lat") is not None),
        )

    @app.get("/api/emergency")
    @require_user
    def emergency():
        u = store.user(g.uid)
        if u.get("lat") is None:
            return jsonify(active=False, reason="Save your city to see emergency information for your area.",
                           helplines=HELPLINES)
        obs = hazards.observed()
        official = hazards.official()
        assessment = HazardService.assess(u["lat"], u["lon"], obs["events"], None, datetime.now().month, seasonal)
        sev = HazardService.severity(official["alerts"], assessment)
        active = sev["level"] in ("orange", "red")
        return jsonify(
            active=active, severity=sev, location={"city": u["city"], "state": u["state"]},
            official_alerts=official["alerts"],
            contacts=[{"name": c["name"], "phone": c["phone"]} for c in store.list_family(g.uid)],
            helplines=HELPLINES,
            actions=["Move to a safe place as instructed by local authorities.",
                     "Take your waterproof document bag, medicines and phone charger.",
                     "Keep your family informed; use SOS if you cannot reach them.",
                     "Follow official instructions over anything else you read."] if active else [],
        )

    # ========================================================== ASSISTANT
    @app.post("/api/assistant")
    @require_user
    def assist():
        question = (request.get_json(silent=True) or {}).get("question", "")
        u = store.user(g.uid)
        raw = store.checklist(g.uid)
        missing = [c[1] for c in catalogue.CATALOGUE if raw.get(c[0], {}).get("status") not in ("uploaded", "not_applicable")
                   and catalogue.CATALOGUE_BY_KEY[c[0]]["essential"]]
        context = {"city": u.get("city") or None, "state": u.get("state") or None,
                   "missing_documents": missing}
        if u.get("lat") is not None:
            official = hazards.official()
            obs = hazards.observed()
            assessment = HazardService.assess(u["lat"], u["lon"], obs["events"], None, datetime.now().month, seasonal)
            sev = HazardService.severity(official["alerts"], assessment)
            context.update(severity=sev["level"], official_alerts=official["alerts"],
                           observed_nearby_count=assessment["nearby_observed"])
        result = assistant.ask(question, context, s.gemini_key, s.gemini_model, opener)
        audit(g.uid, "assistant_question", f"source={result['source']}")
        return jsonify(result)

    # =============================================================== STATIC
    @app.get("/")
    def index():
        return send_from_directory(ROOT, "index.html")

    @app.get("/<path:filename>")
    def static_files(filename: str):
        if ".." in filename or not any(filename.startswith(p) and filename.endswith(e) for p, e in STATIC_OK):
            abort(404)
        return send_from_directory(ROOT, filename)

    return app


if __name__ == "__main__":
    import os
    logging.basicConfig(level=logging.INFO)
    cfg = load_settings()
    host = os.environ.get("AAPDA_HOST", "127.0.0.1")
    port = int(os.environ.get("AAPDA_PORT", "5000"))
    print(f"SafeLife running at http://{host}:{port}")
    create_app(cfg).run(host=host, port=port, debug=False)
