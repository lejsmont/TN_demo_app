# Decisions log

Date: 2026-01-31
- DECISION: UI E2E testing is mandatory using Playwright. RATIONALE: Requirement to validate hosted consent UI flow end-to-end.
- DECISION: Use mastercard-oauth1-signer (official) for OAuth 1.0a signing. RATIONALE: Avoid custom signing complexity and align with Mastercard guidance.
- DECISION: Use oauth1.authenticationutils.load_signing_key (PKCS12) + oauth1.signer.OAuthSigner. RATIONALE: Matches Mastercard signer library expectations for .p12 keystores.
- DECISION: Use requests for HTTP calls. RATIONALE: Minimal dependency, works with OAuth signer and responses mocking.
- DECISION: Use tenacity for retries/backoff on idempotent requests (GET/poll). RATIONALE: Consistent retry policy with clear limits.
- DECISION: Use flask-smorest (apispec) to generate OpenAPI docs. RATIONALE: Built-in Swagger UI and spec generation for Flask.
- DECISION: Use python-dotenv for local env loading. RATIONALE: Simple .env support without hardcoding secrets.
- DECISION: Use responses for HTTP mocking in integration tests. RATIONALE: Simple request-level stubbing for requests.
- DECISION: Store demo data as JSON files with atomic write-then-rename. RATIONALE: Meets no-DB requirement and reduces partial writes.
- DECISION: Pull Consent Management sandbox E2E forward; split original F12 into F12A (consents) and F12B (transaction notifications). RATIONALE: Validate implemented API earlier per user request.
- BLOCKER: Consent Management sandbox returns decrypt.error (publicKeyFingerprint required). Need to add client-side payload encryption (likely Mastercard client-encryption) and configure encryption cert.
- DECISION: Use mastercard-client-encryption (client_encryption) for Consent Management payload encryption with publicKeyFingerprint header. RATIONALE: Required by sandbox for /consents.
- DECISION: Use consent name `notification` per Consent Management tutorial for Transaction Notifications consents. RATIONALE: Sandbox rejects unknown consent names.
- DECISION: Use PyJWT to generate Consent UI JWTs signed with the Mastercard .p12 private key. RATIONALE: Hosted Consent UI requires a signed JWT.
- DECISION: Use Transaction Notifications sandbox transaction simulation (`/notifications/transactions`) with cardReference (not PAN) for posting transactions. RATIONALE: Demo avoids storing PAN and aligns with sandbox simulation endpoint.

- ASSUMPTION: Single-user local demo; no login/roles or multi-tenant behavior.
- ASSUMPTION: App runs on localhost only for demo; no TLS or public hosting requirements.
- ASSUMPTION: Server-rendered HTML (Jinja) with minimal JS; no front-end build pipeline.
- ASSUMPTION: Consents UI redirect returns to a local callback route capturing consent/card identifiers (exact params TBD from docs).
- ASSUMPTION: Demo data stored as JSON files under `./data/` (gitignored), single-process access.
- ASSUMPTION: Use Mastercard sandbox base URLs by default; allow overrides via env vars.
- ASSUMPTION: User will provide sandbox credentials and any required test card data via `.env`/`./credentials/`.
- ASSUMPTION: Test card data is available from the Consent Management testing page (`https://developer.mastercard.com/consent-management/documentation/testing/`) and via the MCP documentation server.
- ASSUMPTION: Notification delivery is asynchronous; app will poll with a bounded timeout and clear failure reason if not found.
- ASSUMPTION: App OpenAPI spec stored in-repo (e.g., `docs/openapi.yaml`).
- ASSUMPTION: Mastercard OAuth 1.0a signing with a keystore-backed private key, per Mastercard docs.
- DECISION: 3DS is in scope, but scheduled as a late/backlog feature after core enrollment + notifications.
- DECISION: Create `plans/000_workflow_state.md` to match required workflow file path (existing `plans/plans_000_workflow_state.md` left intact).
- DECISION: Skip F09 (webhook receiver) and F10 (OpenAPI/Swagger) per user request; proceed directly to UI E2E (F11). RATIONALE: Scope reduction for demo.
