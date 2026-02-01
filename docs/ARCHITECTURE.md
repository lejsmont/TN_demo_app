# Architecture

## Overview
This app is a local Flask web UI with three tabs (enroll, post transactions, dashboard). It integrates with Mastercard Consent Management and Transaction Notifications in sandbox, and stores demo data as JSON files on disk. It uses a small internal client wrapper to handle OAuth 1.0a signing, retries, and error mapping.

## Components
- Web UI (Flask + Jinja): three tabs and forms for enrollment and posting transactions.
  - Templates: `app/templates/layout.html` (shared layout), `app/templates/index.html` (tabs + dashboard),
    `app/templates/consent_ui.html` (hosted Consent UI embed).
  - Index page uses lightweight JS to submit API enrollment form via JSON to `/enroll/api`.
  - Enrollment form includes a sandbox test-card dropdown that prefills card fields.
- API client layer: a Mastercard client module that signs and sends HTTP requests, retries idempotent calls, and normalizes errors.
- Service layer: use-case functions for enrollment, consent UI flow, posting transactions, and checking undelivered notifications.
- Storage layer: JSON file store for enrolled cards, consents, posted transactions, and received notifications.
- Webhook handler (optional): endpoint to receive transaction notification webhooks if a tunnel is used.

## Routes (proposed)
- GET / : landing page with tabs (enroll, post transactions, dashboard) rendered from `index.html`.
- POST /enroll/api : enroll card via API
- GET /enroll/ui/start : start hosted Consent UI flow (renders wrapper with iframe).
- GET /enroll/ui/frame : iframe content that loads ConsentUI.js and posts callback messages.
- GET /enroll/ui/callback : capture consent result and persist enrollment
- GET /enroll/3ds/fingerprint : render 3DS fingerprint iframe page for API-based enrollment
- POST /enroll/3ds/start-authentication : start 3DS authentication after fingerprinting
- GET|POST /enroll/3ds/verify : verify 3DS challenge result and finalize consent
- POST /transactions : post a transaction for an enrolled card
- GET /dashboard : list enrolled cards and notification status (same view as / with dashboard active)
- POST /webhook/transaction-notifications : receive webhook (optional)
- GET /notifications/undelivered : poll undelivered notifications with bounded backoff and store results
- GET /health : simple health check
- GET /api/docs : Swagger UI for app endpoints
- GET /debug/consent-ui-jwt : debug helper to inspect Consent UI JWT (enabled only with MC_DEBUG_CONSENT_UI=1)

## Data storage (filesystem JSON)
All data is stored under ./data (gitignored). Data is write-then-rename for atomic updates.
Storage helpers enforce list-of-dict schemas and block sensitive keys (pan/cvc/cvv) from being persisted.

Proposed files and minimal schemas:
- data/enrollments.json
  - items: { id, consent_id, card_reference, card_alias, pan_last4, status, auth_status, created_at }
- data/transactions.json
  - items: { id, consent_id, card_reference, card_alias, amount, currency, merchant, posted_at, status,
             correlation_id, reference_number, system_trace_audit_number, source }
- data/notifications.json
  - items: { id, card_reference, merchant, amount, currency, event_time, status, received_at,
             reference_number, system_trace_audit_number, trans_uid, notification_sequence_id,
             message_type, encrypted_payload, payload (redacted) }
- data/pending_enrollments.json
  - items: { state, created_at, return_url }
- data/pending_authentications.json
  - items: { state, card_reference, consent_id, card_alias, pan_last4, auth_type, auth_status, auth_params, created_at }
- data/audit.log (optional)
  - append-only text log of actions (no sensitive values)

Notes:
- Hosted UI flow stores a state/nonce to validate callbacks and prevent replay.
- Store only minimal card identifiers (no full PAN). Use PAN only for the API request and discard.
- card_alias can be a user-friendly label like "John D - 0297" (last4 only).

## External integrations
### Consent Management
- Enrollment via API: POST /consents with card details and a consent name; store cardReference + consent id/status.
- Consent name for Transaction Notifications uses the Consent Management tutorial value: `notification`.
- Hosted UI flow: render a wrapper page with an iframe that loads Mastercard Consent UI, then capture callback parameters.
- Hosted UI uses a local page that embeds `ConsentUI.js` with a signed JWT and posts UI messages back to `/enroll/ui/callback`.
- 3DS flow (API enrollment): if `POST /consents` returns auth type THREEDS, run fingerprinting, call
  `/consents/{cardReference}/start-authentication`, and if needed display the challenge iframe and then
  call `/consents/{cardReference}/verify-authentication` to finalize consent.
- Consent payloads are encrypted using Mastercard client-encryption when MC_ENCRYPTION_CERT_PATH is set; encryption metadata (encryptedKey/iv/oaepHashingAlgorithm/publicKeyFingerprint) is included in the payload.

### Transaction Notifications
- Post transaction for enrolled card reference via `/notifications/transactions` (sandbox transaction simulation).
- Each posted transaction includes a generated `referenceNumber` and `systemTraceAuditNumber` to identify UI-originated transactions in notifications.
- Verify delivery using undelivered notifications pull endpoint with bounded retry/backoff; stored notifications are deduped by id.
- Dashboard filters and sorts notifications to show UI-posted transactions newest-first (based on reference/trace numbers or matching card+amount+merchant).
- Webhook endpoint exists but is optional; localhost delivery typically requires a tunnel.
  - Default sandbox base URL: `https://sandbox.api.mastercard.com/openapis` (override via `MC_BASE_URL_TXN_NOTIF`).

## Auth and config
- OAuth 1.0a one-legged authentication using official Mastercard OAuth1 signer library.
- Config via environment variables (see requirements):
  - MC_CONSUMER_KEY
  - MC_KEYSTORE_PASSWORD
  - MC_KEYSTORE_PATH
  - MC_BASE_URL_CONSENTS (optional)
  - MC_BASE_URL_TXN_NOTIF (optional)
- Support for a dry-run validation that checks required env vars and keystore presence.
- App loads `.env` locally via python-dotenv; required variables are validated on demand by the config layer.
- Client retries only idempotent methods (GET/HEAD/OPTIONS); non-idempotent requests are single-shot by default.

## Error handling
- Centralized error mapping in the client layer: HTTP status, reason code, description, correlation id.
- Service layer returns user-friendly messages for the UI, with a short diagnostic id.
- Clear failure messages for missing notifications after polling timeout.

## Logging and redaction
- Use standard logging with structured context (endpoint, status, correlation id).
- Redact PANs, CVC, full consumer key, and OAuth headers.
- Optional audit log for demo actions without sensitive data.

## 3DS support (late feature)
- Adds UI step for 3DS challenge when required.
- Uses test card data from the Consent Management testing page.
- Requires additional callback handling and state tracking in file store.
