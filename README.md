# Consents & Transaction Notifications Demo (Flask)

Local demo web app to enroll cards with Mastercard Consent Management and post test
transactions with Transaction Notifications, then confirm notifications in the sandbox.

## Prerequisites
- Python 3.11+
- pip + venv
- Mastercard sandbox credentials and keystore/certs in `./credentials/`

## Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
pip install -r requirements.txt -r requirements-dev.txt
```

## Configuration
Create `.env` (gitignored) with:
```
MC_CONSUMER_KEY=...
MC_KEYSTORE_PASSWORD=...
MC_KEYSTORE_PATH=./credentials/your-keystore.p12
MC_ENCRYPTION_CERT_PATH=./credentials/your-encryption-cert.crt
```

Optional:
```
MC_BASE_URL_CONSENTS=...
MC_BASE_URL_TXN_NOTIF=...
DATA_DIR=./data
MC_DEBUG_CONSENT_UI=1
```

## Run
```bash
python -m flask --app app run --debug
```
Open http://127.0.0.1:5000

## Tests
```bash
pytest -q
pytest --cov=app --cov-report=term-missing
python -m playwright install
pytest -q -m ui
RUN_E2E=1 pytest -q tests/e2e
```

Notes:
- UI E2E tests are required and use Playwright (headless by default).
- Hosted Consent UI may require manual login/consent in the browser when you run the
  flow interactively.
- API docs (OpenAPI/Swagger) are not generated in this repo (feature was skipped).
