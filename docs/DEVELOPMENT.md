# Development Guide

## Overview
The app is a small Flask/Jinja UI with three tabs (enroll, post, dashboard).
Data is stored locally in JSON files under `./data/` (gitignored).

Key modules:
- `app/mc_client.py`: Mastercard OAuth1 client + error mapping.
- `app/consent_service.py`: Consent Management enrollment helpers.
- `app/transaction_service.py`: Transaction Notifications payloads + identifiers.
- `app/notification_service.py`: Undelivered notifications polling + parsing.

## Environment
Use `.env` for secrets and keep keystores/certs in `./credentials/`.
Required:
- `MC_CONSUMER_KEY`
- `MC_KEYSTORE_PASSWORD`
- `MC_KEYSTORE_PATH`
- `MC_ENCRYPTION_CERT_PATH` (Consent payload encryption)

Optional:
- `MC_BASE_URL_CONSENTS`
- `MC_BASE_URL_TXN_NOTIF`
- `DATA_DIR`

## Run locally
```bash
python -m flask --app app run --debug
```

## Reset demo data
Delete files under `./data/` to clear enrollments/transactions/notifications.

## Tests
```bash
pytest -q
pytest --cov=app --cov-report=term-missing
python -m playwright install
pytest -q -m ui
RUN_E2E=1 pytest -q tests/e2e
```

Tips:
- Use `PW_HEADED=1 pytest -q -m ui` to watch the UI tests.
- If Playwright browsers are missing, rerun `python -m playwright install`.
- E2E tests are safe-by-default and only run with `RUN_E2E=1`.
