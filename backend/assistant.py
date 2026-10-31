"""
Disaster Preparedness Assistant.

Privacy rules enforced here:
  * The model receives only: city, state, severity level, official alert summaries,
    observed hazard summaries, and the NAMES of documents still missing.
  * It never receives vault contents, file names, expiry dates, or identity numbers.

Priority rules:
  * Official instructions (IMD, NDMA/Sachet, CWC, INCOIS, GSI) outrank everything else.
  * If no official alert exists, the assistant says so and does not invent one.
  * Every answer ends with the emergency number 112.

Without GEMINI_API_KEY, or if the API call fails, a rule-based answer is returned.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
TIMEOUT = 20

SYSTEM_PROMPT = (
    "You are SafeLife's disaster preparedness assistant for India. "
    "Rules: (1) If the context contains official alerts from IMD, NDMA/Sachet, CWC, INCOIS or GSI, "
    "quote their instruction exactly, name the agency, and say it comes first. "
    "(2) If the context has no official alert, say that no official warning is active for the location. "
    "Never claim a disaster will happen and never invent alerts or predictions. "
    "(3) Give short, numbered, practical steps. Prefer checklists over long text. "
    "(4) For any immediate danger, tell the user to call 112 right away. "
    "(5) Use only the context provided; do not ask for personal documents or numbers."
)

RULES = [
    (("flood",), "Flood preparation",
     ["Move important documents and medicines to a waterproof bag or a high shelf.",
      "Keep a 3-day supply of drinking water and dry food.",
      "Charge your phone and power bank; keep a torch and spare batteries ready.",
      "Know your nearest high ground and the route to it.",
      "Do not walk or drive through moving floodwater."]),
    (("cyclone", "storm", "wind"), "Cyclone preparation",
     ["Secure loose items outside and close windows and shutters.",
      "Keep identity documents, insurance papers and medical records in one waterproof bag.",
      "Store drinking water, food, first-aid kit and medicines.",
      "Follow evacuation instructions from district authorities immediately."]),
    (("heat", "temperature"), "Heatwave preparation",
     ["Avoid outdoor work between noon and 4 pm.",
      "Drink water regularly, even if not thirsty.",
      "Keep rooms ventilated and shaded; use wet cloth on the neck if needed.",
      "Watch for dizziness, confusion or fainting and seek medical help."]),
    (("earthquake", "quake", "tremor"), "Earthquake preparation",
     ["During shaking: Drop, Cover and Hold On under a sturdy table.",
      "Stay away from windows, mirrors and heavy furniture.",
      "After shaking: check for injuries, gas smell and damaged wiring before moving.",
      "Keep shoes and a torch near your bed."]),
    (("landslide", "hill", "slope"), "Landslide preparation",
     ["Move to higher, stable ground if you hear rumbling or see cracks.",
      "Avoid crossing bridges or drains that are already flooding.",
      "Keep emergency contacts and identity documents ready to carry."]),
    (("document", "papers", "keep", "bag"), "Documents to keep ready",
     ["Identity: Aadhaar, PAN, passport if you have one.",
      "Insurance policy numbers and helpline numbers.",
      "Medical history, prescriptions and blood group proof.",
      "Property papers and bank account details.",
      "Emergency contacts written down on paper as well as on your phone."]),
]


def _fallback(question: str, context: dict) -> dict:
    q = question.lower()
    alerts = context.get("official_alerts") or []
    lines = []
    if alerts:
        for a in alerts:
            lines.append(f"Official ({a.get('issuer', 'agency')}): {a.get('instruction', 'follow the alert')}")
        lines.append("")
    else:
        lines.append("No official warning is active for your location in the sources SafeLife can currently read.")
        lines.append("")

    topic, steps = None, None
    for keywords, name, items in RULES:
        if any(k in q for k in keywords):
            topic, steps = name, items
            break
    if steps is None:
        topic = "General preparation"
        steps = ["Keep identity, insurance and medical documents in one waterproof bag.",
                 "Store 3 days of water, food and medicines.",
                 "Save emergency contacts on paper too.",
                 "Check official alerts on NDMA Sachet, IMD and your state disaster management website."]
    lines.append(f"{topic}:")
    lines.extend(f"{i}. {s}" for i, s in enumerate(steps, 1))

    missing = context.get("missing_documents") or []
    if missing and ("document" in q or "keep" in q or "papers" in q or "bag" in q):
        lines.append("")
        lines.append("Documents still missing in your checklist: " + ", ".join(missing[:6]) + ".")

    lines.append("")
    lines.append("In immediate danger, call 112.")
    return {"answer": "\n".join(lines), "source": "rules", "model": None}


def ask(question: str, context: dict, api_key: str | None, model: str, opener=None) -> dict:
    question = (question or "").strip()[:1000]
    if not question:
        raise ValueError("Please type a question.")
    if not api_key:
        return _fallback(question, context)

    prompt = (
        "Context (may be empty):\n" + json.dumps(context, ensure_ascii=False, indent=1)
        + "\n\nUser question: " + question
    )
    body = json.dumps({
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 600},
    }).encode()
    req = urllib.request.Request(
        GEMINI_URL.format(model=model), data=body, method="POST",
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
    )
    try:
        with (opener or urllib.request.urlopen)(req, timeout=TIMEOUT) as resp:
            data = json.loads(resp.read().decode())
        text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        return {"answer": text + "\n\nIn immediate danger, call 112.", "source": "gemini", "model": model}
    except (OSError, KeyError, IndexError, TypeError, ValueError):
        # OSError covers URLError, HTTPError, socket timeouts and connection resets.
        fb = _fallback(question, context)
        fb["note"] = "The AI service is unavailable right now, so this is a rule-based answer."
        return fb
