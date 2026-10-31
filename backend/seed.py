"""
Seed script for SafeLife to populate Himangi's profile and sample data.
"""
from __future__ import annotations
import json
import time
from werkzeug.security import generate_password_hash

def seed_himangi(store, blobs=None):
    email = "himangi123@gmail.com"
    
    # 1. Check or create user
    with store._lock:
        row = store._db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if row:
            uid = row[0]
        else:
            now = time.time()
            cur = store._db.execute(
                "INSERT INTO users (email, pw_hash, full_name, state, city, lat, lon, blood_group, profile_json, created) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (email, generate_password_hash("Password@123"), "Himangi", "Delhi", "New Delhi", 28.6139, 77.2090, "B+",
                 json.dumps({"has_property": True, "has_children": True, "has_elderly": True, "lives_flood_zone": False, "has_health_condition": True, "has_vehicle": True, "has_education_records": True}),
                 now)
            )
            try:
                store._db.commit()
            except Exception:
                pass
            uid = cur.lastrowid

    # 2. Update profile to New Delhi & Himangi
    try:
        store.update_profile(uid, full_name="Himangi", city="New Delhi", state="Delhi", lat=28.6139, lon=77.2090, blood_group="B+")
    except Exception:
        pass
    
    # 3. Set checklist
    checklist_data = {
        "aadhaar": "uploaded",
        "pan": "uploaded",
        "passport": "uploaded",
        "voter_id": "uploaded",
        "driving_licence": "uploaded",
        "birth_certificate": "uploaded",
        "medical_history": "uploaded",
        "prescriptions": "uploaded",
        "blood_group": "uploaded",
        "health_insurance": "pending",
        "bank_info": "uploaded",
        "insurance": "uploaded",
        "property_papers": "uploaded",
        "vehicle_rc": "uploaded",
        "financial_records": "pending",
        "certificates": "uploaded",
        "degree": "uploaded",
        "marksheets": "pending",
        "emergency_contacts": "uploaded",
        "family_info": "uploaded",
        "family:meeting_point": "uploaded",
        "supply:water": "uploaded",
        "supply:firstaid": "uploaded",
        "supply:torch": "uploaded",
    }
    for k, status in checklist_data.items():
        try:
            store.set_checklist(uid, k, status)
        except Exception:
            pass
        
    # 4. Check vault items count; if < 12, add items
    try:
        items = store.list_items(uid)
        if len(items) < 12:
            now = time.time()
            docs = [
                ("Aadhaar Card.pdf", "aadhaar", 1024 * 340),
                ("PAN Card.pdf", "pan", 1024 * 210),
                ("Passport Front & Back.pdf", "passport", 1024 * 850),
                ("Driving Licence.pdf", "driving_licence", 1024 * 180),
                ("Medical History Summary.pdf", "medical_history", 1024 * 420),
                ("Prescription & Allergy Card.pdf", "prescriptions", 1024 * 160),
                ("Blood Group Lab Report.pdf", "blood_group", 1024 * 110),
                ("Life Insurance Policy.pdf", "insurance", 1024 * 920),
                ("Property Agreement.pdf", "property_papers", 1024 * 1450),
                ("Vehicle Registration Certificate.pdf", "vehicle_rc", 1024 * 230),
                ("University Degree Certificate.pdf", "degree", 1024 * 670),
                ("Bank Passbook & Cancelled Cheque.pdf", "bank_info", 1024 * 310),
            ]
            with store._lock:
                for i, (name, doc_key, size) in enumerate(docs):
                    if i >= len(items):
                        dummy_meta = f"demo_meta_{doc_key}:{name}"
                        dummy_ref = f"blob_{uid}_{i+1}"
                        store._db.execute(
                            "INSERT INTO vault_items (user_id, meta, blob_ref, size, created) VALUES (?, ?, ?, ?, ?)",
                            (uid, dummy_meta, dummy_ref, size, now - (12 - i) * 86400)
                        )
                try:
                    store._db.commit()
                except Exception:
                    pass
    except Exception:
        pass

    # 5. Seed events
    try:
        now = time.time()
        with store._lock:
            store._db.execute("DELETE FROM events WHERE user_id = ?", (uid,))
            store._db.execute("INSERT INTO events (user_id, kind, detail, created) VALUES (?, ?, ?, ?)",
                             (uid, "document_uploaded", "Aadhaar Card.pdf", now - 2 * 3600))
            store._db.execute("INSERT INTO events (user_id, kind, detail, created) VALUES (?, ?, ?, ?)",
                             (uid, "vault_accessed", "by you", now - 3 * 3600))
            store._db.execute("INSERT INTO events (user_id, kind, detail, created) VALUES (?, ?, ?, ?)",
                             (uid, "alert_checked", "Heat Wave - Delhi", now - 5 * 3600))
            try:
                store._db.commit()
            except Exception:
                pass
    except Exception:
        pass

    # 6. Seed family members
    try:
        fam = store.list_family(uid)
        if not fam:
            store.add_family(uid, "Rajesh Sharma", "Father", "+91 98765 43210", "rajesh@gmail.com")
            store.add_family(uid, "Sunita Sharma", "Mother", "+91 98765 43211", "sunita@gmail.com")
            store.add_family(uid, "Rahul Sharma", "Brother", "+91 98765 43212", "rahul@gmail.com")
    except Exception:
        pass

    return uid
