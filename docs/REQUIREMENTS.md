# Requirements — Consents & Transaction Notifications Demo (Flask)

## 1) Project overview
**Name**: Consents and Transaction Notification Demo  
**Goal**: A local demo web app that (a) enrolls cards via Mastercard Developers **Consent Management** and (b) posts transactions via **Transaction Notifications**, then verifies notifications end‑to‑end in the sandbox. fileciteturn1file0

**Target users**: internal/demo usage.
- ASSUMPTION: Single-user local demo; no login/roles or multi-tenant behavior.
- ASSUMPTION: Runs on localhost only (no public hosting or TLS requirements for the demo).

## 2) Technology stack (preferred)
- Python **3.11+**
- Flask **3.x**
- Tests: **pytest** (target **>80%** coverage) fileciteturn1file0
- ASSUMPTION: Server-rendered HTML (Jinja) with minimal JS; no front-end build pipeline.

## 3) MVP functional requirements
### 3.1 Web UI (3 tabs)
1) **Card enrollment**
   - Enrollment using API
   - Enrollment using Consents UI (hosted / redirect flow)
   - ASSUMPTION: Redirect flow returns to a local callback route that captures consent/card identifiers.
2) **Post card transactions**
   - Dropdown list of enrolled cards
3) **Dashboard**
   - List enrolled cards
   - List transaction notifications received/confirmed fileciteturn1file0

### 3.2 Data storage
- Store demo data in **static files in the filesystem** (no DB). fileciteturn1file0
- ASSUMPTION: JSON files under a local `./data/` directory (gitignored), with simple schemas.
- ASSUMPTION: Single-process access; no concurrent writers.

### 3.3 External APIs
- Use Mastercard Developers APIs:
  - Consent Management (Consents)
  - Transaction Notifications fileciteturn1file0
- ASSUMPTION: Use Mastercard sandbox base URLs by default; allow overrides via env vars.

### 3.4 User flows (E2E)
1) User enrolls a card
2) System confirms enrollment and shows the card on the dashboard
3) User posts a transaction for an enrolled card
4) System confirms transaction posted
5) System checks “undelivered notifications” endpoint (or equivalent) and confirms the posted transaction appears (or reports a clear reason if not found) fileciteturn1file0
- ASSUMPTION: Notification delivery is asynchronous; app will poll with a bounded timeout and clear failure reason if not found.

## 4) Documentation requirements
- OpenAPI/Swagger for the app endpoints
- README setup instructions
- Development guide
- Deployment guide (local) fileciteturn1file0
- ASSUMPTION: App OpenAPI spec stored in-repo (e.g., `docs/openapi.yaml`).

## 5) Deployment requirements
- Environment: **Sandbox**
- Hosting: **local host** fileciteturn1file0

## 6) Authentication and credentials (DO NOT COMMIT)
Authentication can be tricky—prefer documented approaches and existing libraries first. fileciteturn1file0
ASSUMPTION: Mastercard OAuth 1.0a signing with a keystore-backed private key, per Mastercard docs.

### 6.1 Environment variables
Put secrets in `.env` (gitignored), e.g.:

- `MC_CONSUMER_KEY=...`
- `MC_KEYSTORE_PASSWORD=...`
- `MC_KEYSTORE_PATH=./credentials/<your-keystore-file-or-folder>`
- (Optionally) `MC_BASE_URL_CONSENTS=...`
- (Optionally) `MC_BASE_URL_TXN_NOTIF=...`
- ASSUMPTION: User will provide sandbox credentials and any required test card data via `.env`/`./credentials/`.
- ASSUMPTION: Test card data is available from the Consent Management testing page (`https://developer.mastercard.com/consent-management/documentation/testing/`) and via the MCP documentation server.

### 6.2 Local credentials folder
- Store keystore/certs under `./credentials/` (gitignored).

## 7) Assumption policy (for Codex autonomy)
When details are unclear:
- Codex should **make a reasonable assumption**, proceed, and record it in `docs/DECISIONS.md`.
- Codex should ask the user **only when blocked**, when two choices are mutually exclusive, or when the choice affects security/cost/external behavior significantly.

## 8) Success criteria
- [ ] All MVP features implemented fileciteturn1file0
- [ ] Real end‑to‑end sandbox API tests (successful responses + relevant data) fileciteturn1file0
- [ ] Successful test using the Web UI fileciteturn1file0
- [ ] All tests passing; target >80% coverage fileciteturn1file0
- [ ] API documentation complete fileciteturn1file0
- [ ] User acceptance testing completed fileciteturn1file0

## 9) Explicitly deferred / optional scope
### 9.1 3DS (clarify before implementing)
The original idea mentions “3DS implementation with all steps”.
In-scope for this project: **3DS IS IN SCOPE**, but scheduled as a **late/backlog feature** after core enrollment + notifications work.

## 10) Risks & open questions
- Risk: 3DS flow integration may require additional callbacks/UI steps and sandbox-specific parameters.
- Risk: Sandbox credentials/test cards are required for E2E; missing access will block verification.
- Risk: Hosted consent UI may require manual human interaction (login/consent/MFA) during demo flows.
- Risk: Mastercard sandbox availability/latency could impact E2E notification verification.
- Risk: Exact Consent UI redirect/callback parameters may differ by product/version and require validation.
- Risk: “Undelivered notifications” endpoint semantics may vary; may need retries/backoff guidance from docs.
- Risk: Keystore format (JKS vs PKCS12) and OAuth signing library compatibility may require adjustment.
- Risk: Static file storage without locking could be fragile if the demo is run with multiple workers.
