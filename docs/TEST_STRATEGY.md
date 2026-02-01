# Test Strategy

## Goals
- Validate core flows (enroll, post transaction, verify notifications).
- Maintain >80% coverage target.
- Keep E2E safe-by-default and gated.

## Test layers
### Unit tests
Focus: pure logic and helpers.
- File storage read/write and atomic update behavior.
- Input validation and mapping.
- Error mapping and redaction helpers.

### Integration tests (Flask test client)
Focus: app routes and service wiring with external calls mocked.
- POST /enroll/api returns expected UI status.
- GET /enroll/ui/start renders wrapper with iframe for Consent UI.
- GET /enroll/ui/frame renders ConsentUI.js with expected inputs.
- POST /enroll/ui/callback persists enrollment.
- Hosted Consent UI start renders ConsentUI.js and stores pending state.
- GET / renders tabs and expected UI elements.
- GET /debug/consent-ui-jwt is gated and returns decoded header/payload when enabled.
- POST /transactions posts a sandbox transaction simulation using mocked Transaction Notifications API.
- GET /notifications/undelivered polls mocked undelivered notifications and stores results.
- GET /notifications/undelivered reconciles notifications.
- 3DS flow endpoints are exercised with mocked Consent API (fingerprint -> start-auth -> challenge -> verify).
 - Consent Management API enrollment mocked via responses.

Mocking approach:
- Use responses (or requests-mock) to fake Mastercard HTTP responses.
- No real credentials required for unit/integration tests.

### E2E tests (real sandbox)
Gated by RUN_E2E=1.
- Validate required env vars and keystore presence.
- Minimal happy path for Consent Management enrollment.
- Post a transaction and poll undelivered notifications until the transaction is found or a timeout occurs.
- Consent Management E2E uses test card data to POST /consents in sandbox.
- Consent Management sandbox may require payload encryption (publicKeyFingerprint); configure client encryption before E2E.

E2E contract:
- Skip with clear reason if env vars missing.
- Use short, bounded polling with backoff.
- Log correlation ids and error codes with sensitive values redacted.
- 3DS flow E2E added when implemented; may require manual step.

### UI E2E (required, Playwright)
- UI E2E coverage is mandatory for the hosted Consent UI flow and dashboard verification.
- If hosted consent UI requires manual steps (login/consent/MFA), stop and prompt user.
- Headless by default, enable headed via PW_HEADED=1.

## Commands
- Unit and integration: pytest -q
- Coverage: pytest --cov=app --cov-report=term-missing
- E2E: RUN_E2E=1 pytest -q tests/e2e
- UI E2E: pytest -q -m ui (requires `pip install playwright pytest-playwright` + `playwright install`)

## Required env vars for E2E
- MC_CONSUMER_KEY
- MC_KEYSTORE_PASSWORD
- MC_KEYSTORE_PATH
- MC_ENCRYPTION_CERT_PATH (Consent Management payload encryption)
- MC_BASE_URL_CONSENTS (optional)
- MC_BASE_URL_TXN_NOTIF (optional)

## Test data
- Use test card data from Consent Management testing page via MCP docs.
