"""
Document catalogue, personalised recommendations, and the Emergency Readiness Score.

Recommendations are rule-based and explainable: every suggested document comes with
the answer that triggered it and how it helps in an emergency. No generated text is
presented as an official instruction.
"""
from __future__ import annotations

# key, label, group, essential, why it matters, how it helps during an emergency
CATALOGUE = [
    ("aadhaar", "Aadhaar Card", "Identity", True,
     "Primary national ID, needed for almost every government service.",
     "Proof of identity at relief camps and for claiming compensation or aid."),
    ("pan", "PAN Card", "Identity", False,
     "Needed for banking, tax filings and large financial transactions.",
     "Lets you access and move money quickly when branches are disrupted."),
    ("passport", "Passport", "Identity", False,
     "Main travel document and a widely accepted photo ID.",
     "Identity proof if you must evacuate across state or national borders."),
    ("voter_id", "Voter ID", "Identity", False,
     "Accepted photo ID and proof of residence in many places.",
     "Supporting address proof for relief and re-registration after displacement."),
    ("driving_licence", "Driving Licence", "Identity", False,
     "Photo ID and proof of driving eligibility.",
     "Identity proof and needed if you must drive a vehicle out of an affected area."),
    ("certificates", "Educational Certificates", "Education", False,
     "Proof of qualifications for jobs and admissions.",
     "Needed to rebuild your records after losing originals in a flood or fire."),
    ("marksheets", "Mark Sheets", "Education", False,
     "Academic record used in admissions and job applications.",
     "Rebuilds your academic history if originals are destroyed."),
    ("degree", "Degree Certificates", "Education", False,
     "Proof of degrees for employment and further study.",
     "Hard to replace quickly, so a digital copy speeds up re-issue requests."),
    ("bank_info", "Bank Account Information", "Financial", True,
     "Account numbers, IFSC and branch details.",
     "Lets you receive relief payments and contact your bank if cards are lost."),
    ("insurance", "Insurance Policies", "Financial", True,
     "Health, life, vehicle and home policy documents with claim numbers.",
     "Insurers need policy numbers and helplines to start a claim quickly."),
    ("property_papers", "Property Documents", "Financial", True,
     "Sale deed, registry, rent agreement and property tax receipts.",
     "Proves ownership or tenancy when claiming damage compensation."),
    ("financial_records", "Important Financial Records", "Financial", False,
     "Loan papers, FD/PPF receipts and tax filings.",
     "Shows what you owe and what you hold, which matters for relief and insurance."),
    ("medical_history", "Medical History", "Medical", True,
     "Conditions, surgeries, allergies and current treatment.",
     "Doctors at relief camps need this to treat you safely without guessing."),
    ("prescriptions", "Prescriptions", "Medical", True,
     "Current medicines with dosage and doctor details.",
     "Lets you get medicine replaced if your supply is lost or damaged."),
    ("blood_group", "Blood Group Information", "Medical", True,
     "Your blood group, confirmed by a lab report or card.",
     "Critical for emergency transfusions when there is no time to test."),
    ("health_insurance", "Health Insurance Documents", "Medical", True,
     "Card, policy and TPA or hospital network details.",
     "Enables cashless treatment at network hospitals during an emergency."),
    ("emergency_contacts", "Emergency Contact Details", "Emergency", True,
     "Names and numbers of people to call, including out-of-state contacts.",
     "Lets others know you are safe, and lets responders reach your family."),
    ("family_info", "Family Member Information", "Emergency", True,
     "Family names, ages, relations and any special needs.",
     "Helps responders account for everyone in the household."),
    ("legal_docs", "Important Legal Documents", "Emergency", False,
     "Will, power of attorney, guardianship or custody papers.",
     "Establishes who can act for you or for dependants when you cannot."),
    ("ownership_records", "Property Ownership Records", "Emergency", False,
     "Land records, society or building ownership proofs.",
     "Confirms your claim on property for insurers and government relief."),
    ("vehicle_rc", "Vehicle Registration (RC)", "Financial", False,
     "Registration certificate for each vehicle you own.",
     "Needed for insurance claims and to prove ownership after flood damage."),
    ("birth_certificate", "Children's Birth Certificates", "Identity", False,
     "Proof of age and parentage for each child.",
     "Required to prove guardianship and to re-enrol children in school after displacement."),
]

CATALOGUE_BY_KEY = {k: {"key": k, "label": l, "group": g, "essential": e, "why": w, "helps": h}
                    for k, l, g, e, w, h in CATALOGUE}

SUPPLIES = [
    ("supply:water", "Drinking water (3 litres per person per day, 3 days)"),
    ("supply:food", "Non-perishable food for 3 days"),
    ("supply:torch", "Torch and spare batteries"),
    ("supply:firstaid", "First-aid kit and essential medicines"),
    ("supply:power", "Power bank and charging cable"),
    ("supply:cash", "Some cash in small notes"),
    ("supply:whistle", "Whistle and a waterproof bag for documents"),
]

FAMILY_PLAN_KEY = "family:meeting_point"


def recommend(answers: dict) -> list[dict]:
    """Return recommended document keys with the reason each one was suggested."""
    recs: dict[str, list[str]] = {}

    def add(key: str, reason: str) -> None:
        recs.setdefault(key, []).append(reason)

    for key in ("aadhaar", "bank_info", "insurance", "emergency_contacts", "family_info"):
        add(key, "Everyone needs this for identity, money or contact during an emergency.")
    if answers.get("has_vehicle"):
        add("vehicle_rc", "You told us you own a vehicle; insurance claims need its registration.")
        add("insurance", "You own a vehicle, so motor insurance papers matter.")
    if answers.get("has_property"):
        add("property_papers", "You own or rent property; ownership proof is needed for damage claims.")
        add("ownership_records", "Property ownership records speed up insurance and relief claims.")
    if answers.get("has_children"):
        add("birth_certificate", "You have children; their birth certificates prove guardianship.")
        add("legal_docs", "Guardianship papers are important if you are separated from children.")
    if answers.get("has_elderly"):
        add("medical_history", "Someone in your home is elderly; their medical history helps doctors act fast.")
        add("prescriptions", "Elderly members often need regular medicines that are hard to replace.")
    if answers.get("has_health_condition"):
        add("medical_history", "You reported a health condition; responders need it to treat you safely.")
        add("prescriptions", "Ongoing treatment means missing doses are risky after a disaster.")
    if answers.get("lives_flood_zone"):
        add("passport", "If you may need to evacuate beyond your state, a photo ID that travels helps.")
        add("property_papers", "Flood-prone areas see frequent damage claims; keep ownership proof handy.")
    if answers.get("has_education_records"):
        add("certificates", "Originals are hard to replace; keep digital copies.")
    add("blood_group", "A confirmed blood group saves time in an emergency transfusion.")

    return [
        {"key": k, "label": CATALOGUE_BY_KEY[k]["label"], "reasons": v,
         "helps": CATALOGUE_BY_KEY[k]["helps"], "essential": CATALOGUE_BY_KEY[k]["essential"]}
        for k, v in recs.items() if k in CATALOGUE_BY_KEY
    ]


def readiness(user: dict, checklist: dict[str, dict], family_count: int, vault_count: int) -> dict:
    """
    Emergency Readiness Score out of 100. Each part is listed with what earned it,
    so the user can see how to improve.
    """
    parts = []

    essential = [k for k in CATALOGUE_BY_KEY if CATALOGUE_BY_KEY[k]["essential"]]
    done = sum(1 for k in essential
               if checklist.get(k, {}).get("status") in ("uploaded", "not_applicable"))
    doc_pts = round(40 * done / len(essential), 1)
    parts.append({"name": "Essential documents", "max": 40, "points": doc_pts,
                  "detail": f"{done} of {len(essential)} essential documents uploaded or marked not applicable",
                  "tip": "Upload or mark each essential document in the Document Recommendations page."})

    contacts_pts = round(20 * min(family_count, 3) / 3, 1)
    parts.append({"name": "Emergency contacts", "max": 20, "points": contacts_pts,
                  "detail": f"{family_count} contact{'s' if family_count != 1 else ''} saved (3 is the target)",
                  "tip": "Add at least three people who can be reached if phone lines are down."})

    supply_done = sum(1 for k, _ in SUPPLIES if checklist.get(k, {}).get("status") == "uploaded")
    supply_pts = round(15 * supply_done / len(SUPPLIES), 1)
    parts.append({"name": "Emergency supplies", "max": 15, "points": supply_pts,
                  "detail": f"{supply_done} of {len(SUPPLIES)} supply items ready",
                  "tip": "Tick off supplies in the Emergency Planner as you prepare them."})

    loc_pts = 10.0 if user.get("city") and user.get("state") else 0.0
    parts.append({"name": "Location set", "max": 10, "points": loc_pts,
                  "detail": "City and state saved" if loc_pts else "No city or state saved",
                  "tip": "Save your city and state so alerts can be matched to your area."})

    meeting = checklist.get(FAMILY_PLAN_KEY, {}).get("status") == "uploaded"
    family_pts = 10.0 if meeting else 0.0
    parts.append({"name": "Family plan", "max": 10, "points": family_pts,
                  "detail": "Meeting point agreed" if meeting else "No family meeting point recorded",
                  "tip": "Agree on one meeting point and mark it done in the Emergency Planner."})

    med_pts = 5.0 if user.get("blood_group") else 0.0
    parts.append({"name": "Medical basics", "max": 5, "points": med_pts,
                  "detail": "Blood group saved" if med_pts else "Blood group not saved",
                  "tip": "Save your blood group in your profile."})

    total = round(sum(p["points"] for p in parts))
    return {"score": total, "max": 100, "parts": parts, "vault_documents": vault_count}
