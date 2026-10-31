# SafeLife — Your Memories. Your Documents. Your Safety.

An AI-assisted personal memory vault and disaster awareness platform for India.

- **Vault:** important documents encrypted on your device before upload.
- **AapdaSense:** observed hazards, official-source status, and a transparent risk assessment for your city.
- **Preparedness:** document checklist with reasons, emergency readiness score, family safety, and Emergency Mode.

> SafeLife is an awareness tool, **not** an official warning service. In an emergency call **112**.
> Official alerts come from NDMA Sachet, IMD, CWC, INCOIS and GSI.

## Quick start

```bash
pip install -r requirements.txt
cp .env.example .env          # then edit .env (see "Configuration")
python app.py                 # open http://127.0.0.1:5000
```

Run the tests (no network needed):

```bash
pytest -q
```

## Configuration

Copy `.env.example` to `.env` and fill in your own values. `.env` is ignored by git. Never commit it or paste its values into chats, screenshots or tickets.

| Variable | Required | What it does |
|---|---|---|
| `AAPDA_SECRET_KEY` | yes | Long random string. Generate: `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `AAPDA_COOKIE_SECURE` | yes | `false` on `http://localhost`, `true` when served over HTTPS |
| `AAPDA_VAULT_DB` | no | SQLite file for accounts, metadata and (if Supabase is off) encrypted file bodies |
| `AAPDA_SUPABASE_URL` | no | Use the **project URL** `https://<project-ref>.supabase.co`, not the dashboard link |
| `AAPDA_SUPABASE_SERVICE_ROLE_KEY` | no | Server-only key for a **private** Supabase Storage bucket |
| `AAPDA_SUPABASE_BUCKET` | no | Bucket name (default `safelife-vault`) |
| `AAPDA_VAULT_ENCRYPTION_KEY` | no | Fernet key for an extra server-side layer on stored data. Back it up: losing it makes wrapped data unreadable |
| `GEMINI_API_KEY` | no | Enables the AI assistant. Without it, rule-based answers are used |
| `GEMINI_MODEL` | no | Default `gemini-2.5-flash` |
| `AAPDA_*_FEED_URL` | no | Official feed URLs. Parsers are not built yet, so these show "pending parser" |

### Supabase Storage setup (optional)
1. Create a project at supabase.com. Under **Storage**, create a **private** bucket named `safelife-vault`.
2. Put the project URL and the **service_role** key in `.env`. Keep that key on the server only.
3. Restart the app. Vault file bodies are then stored in the private bucket. Every download still goes through SafeLife and checks your session.

Supabase upload, download and delete calls use the Storage REST API. They are covered by tests with a fake transport, but **not yet tested against a live project**. Check one upload in your own project first.

### Rotating exposed keys
If a key has appeared in a chat, screenshot or public place, rotate it now:
- Supabase: Project Settings → API → regenerate the service_role key.
- Google AI Studio: delete the key and create a new one.

## How the vault stays private

| Layer | What happens |
|---|---|
| Login password | Hashed with scrypt. It only opens your account. |
| Second step (MFA) | Optional TOTP authenticator (RFC 6238). Secret is wrapped at rest when the Fernet key is set. |
| Vault passphrase | Never sent to the server. Turns into an AES-256 key with PBKDF2-SHA256 (600,000 iterations) in your browser. |
| Each file | Encrypted with AES-256-GCM and a fresh random IV. File name, category, expiry date and hash are inside the encrypted metadata. |
| Server | Stores ciphertext only. Optional Fernet wrapping adds a second layer. |
| Session | HttpOnly, SameSite=Strict cookie, 7-day expiry. Scripts cannot read it. |
| Lock | Key lives in memory only. Vault locks on sign-out, on reload, or after 10 minutes idle. |

**If you forget the vault passphrase, your documents cannot be recovered.** This is what makes the encryption real.

What the server can see: your account email, which document *types* you marked as uploaded (for example "Aadhaar: uploaded"), family contacts you add, and an access history (uploads, downloads, deletions, sign-ins). It cannot see document names, contents, or expiry dates.

Other protections: CSRF header required on every state-changing API call, login rate limit (8 failures per email, then a 15-minute lock), strict security headers and Content-Security-Policy, and no access to the database, source code or model files over HTTP.

## Module status

| Module | Status | Notes |
|---|---|---|
| Sign up, login, sessions | Done | Cookie session, rate limiting |
| Two-step verification (TOTP) | Done | Enable, disable and login step. Tested against the RFC 6238 vector |
| Personalised checklist | Done | Onboarding questions produce recommendations, each with its reason and how it helps |
| Document status (uploaded / pending / not applicable) | Done | Uploading a document marks its type as uploaded |
| Encrypted vault: upload, open, download, delete | Done | Verified end-to-end in a real browser |
| Duplicate detection | Done | Runs in the browser on decrypted hashes, so the server never compares files |
| Expiry dates and renewal reminders | Done | You enter the date. Reminders are calculated in the browser |
| Access history and audit log | Done | Shown in the vault and on the dashboard |
| Permanent deletion (single file and whole account) | Done | Account deletion also purges stored file bodies |
| Auto-classification from filename | Partial | Suggests a document type from the file name. You confirm it |
| OCR (reading text from scans) | Not built | Needs an OCR engine. Shown as a note in the vault |
| Live hazard monitoring (USGS, NASA EONET, Open-Meteo) | Done | Cached, and one failing source does not stop the others |
| Official alerts (IMD, NDMA Sachet, CWC, INCOIS, GSI) | Not connected | Status is shown honestly. No alerts are invented. Parsers need to be written against each agency's live feed |
| Severity levels: green, yellow, orange, red | Done | Red comes only from an official alert. Observed hazards reach orange at most |
| Risk assessment with visible factors | Done | Heuristic, not a prediction. Every point is listed |
| Interactive India map | Done | Leaflet with OpenStreetMap tiles. Falls back to a city list if the map cannot load |
| State and district choropleth | Not built | Needs boundary data. Current map shows events and cities |
| Personalised alert notifications (push / SMS) | Not built | Alerts are shown in the app. No push or SMS provider is configured |
| AI preparedness assistant | Done | Gemini when a key is set. Otherwise rule-based. Official alerts come first. Vault contents are never sent |
| Emergency readiness score | Done | Out of 100, with a breakdown and tips |
| Family network: contacts, SOS, check-ins | Done | SOS and check-ins are recorded and show contacts to call. The server does not send SMS |
| Emergency Mode | Done | Turns on at orange or red for your saved city. Helplines are listed with links |
| Share location during emergencies | Not built | Needs a consent flow and an opt-in location feature |
| Per-document emergency access for family | Not built | Deliberately not added yet. Sharing needs its own consent and audit design |
| Sign in with Google | Not built | |
| Forgot password / recovery | Not built | Needs recovery codes or an email provider. Account deletion is available now |

## Project layout

```
safelife-app/
├── app.py                  # Flask routes, security headers, CSRF guard, static serving
├── backend/
│   ├── config.py           # .env loader and settings (no secrets in code)
│   ├── security.py         # TOTP (RFC 6238), Fernet wrapping helper
│   ├── store.py            # SQLite: accounts, sessions, checklist, vault metadata, family, events
│   ├── blobs.py            # Encrypted file bodies: SQLite or private Supabase Storage
│   ├── catalogue.py        # Document catalogue, recommendations, readiness score
│   ├── hazards.py          # AapdaSense: observed feeds, official registry, assessment, severity
│   └── assistant.py        # Gemini call or rule-based answers; privacy rules enforced here
├── index.html              # Single-page shell
├── css/app.css             # Light design system (purple and orange accents)
├── js/
│   ├── vault-crypto.js     # Browser encryption (PBKDF2 + AES-256-GCM)
│   ├── api.js              # API client, escaping, formatting
│   ├── views-auth.js       # Sign in, sign up, MFA step, onboarding
│   ├── views-main.js       # Dashboard, AapdaSense, map, documents, planner, family, emergency, settings
│   ├── views-vault.js      # Memory Vault and AI Assistant
│   └── app.js              # Router, navigation, session handling
├── data/Natural_Disasters_in_India_.csv   # Used only for the monthly seasonal term
├── tests/test_app.py       # Backend tests (no network)
├── .env.example            # Placeholders only
└── requirements.txt
```

## API overview

All state-changing calls (`POST`, `PUT`, `DELETE`) need the header `X-SafeLife: 1`. The browser app sends it automatically.

| Area | Routes |
|---|---|
| Auth | `POST /api/auth/register`, `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me`, `POST /api/auth/mfa/setup`, `POST /api/auth/mfa/enable`, `POST /api/auth/mfa/disable` |
| Account | `DELETE /api/account` (body `{"confirm":"DELETE"}`) |
| Profile | `GET/PUT /api/profile`, `POST /api/onboarding`, `GET /api/recommendations` |
| Checklist | `GET /api/checklist`, `PUT /api/checklist/<key>` |
| Vault | `GET /api/vault/setup`, `PUT /api/vault/check`, `GET/POST /api/vault/items`, `GET/DELETE /api/vault/items/<id>`, `GET /api/vault/history` |
| Family | `GET/POST /api/family`, `DELETE /api/family/<id>`, `POST /api/family/sos`, `POST /api/family/checkin`, `GET /api/family/events` |
| AapdaSense | `GET /api/aapdasense/overview`, `GET /api/aapdasense/location?city=`, `GET /api/aapdasense/map`, `GET /api/hazards/cities` |
| Dashboard | `GET /api/dashboard`, `GET /api/readiness`, `GET /api/emergency` |
| Assistant | `POST /api/assistant` (body `{"question": "..."}`) |

## Testing

- `tests/test_app.py` covers auth, MFA, CSRF, vault isolation and encryption at rest, the Supabase adapter (with a fake transport), account deletion, validation, the severity rules, the assistant's privacy and fallback behaviour, and static file rules.
- The browser flow was tested end-to-end with Playwright: sign up, onboarding, vault setup, upload, lock, wrong passphrase, unlock, download (bytes match), checklist update, family SOS, MFA enable and sign-in, and the assistant.

## Limits you should know about

- Vault cryptography has not been audited by a third party. Get a review before storing sensitive personal documents at scale.
- Official agency feeds are not parsed yet. Until they are, SafeLife cannot show official red alerts. The app says so instead of guessing.
- Observed hazards and the risk assessment are awareness signals. They are not predictions and not official warnings.
- The app does not send SMS or push notifications yet.
- Without an encryption key set, the server stores only what the browser encrypted. Set `AAPDA_VAULT_ENCRYPTION_KEY` to add a second layer.
- Use HTTPS in production. The vault's browser encryption needs a secure context, and the session cookie is Secure only over HTTPS.
