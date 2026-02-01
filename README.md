# Consents & Transaction Notifications Demo (Flask)

Local demo web app to enroll cards with Mastercard Consent Management, post test
transactions with Transaction Notifications, and confirm notifications in the sandbox.

## Prerequisites
- Python 3.11+
- pip + venv
- Mastercard sandbox credentials and keystore/certs placed in `./credentials/`

## Step-by-step setup (from a fresh clone)

### 1) Clone and enter the repo
```bash
git clone https://github.com/lejsmont/TN_demo_app.git
cd TN_demo_app
```

### 2) Create and activate a virtual environment
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
pip install -r requirements.txt -r requirements-dev.txt
```

### 3) Add credentials
Copy your Mastercard sandbox keystore and encryption certs into `./credentials/`.

### 4) Configure environment
Create a `.env` file (gitignored) with the required settings:
```
MC_CONSUMER_KEY=...
MC_KEYSTORE_PASSWORD=...
MC_KEYSTORE_PATH=./credentials/your-keystore.p12
MC_ENCRYPTION_CERT_PATH=./credentials/your-encryption-cert.crt
```

Optional settings:
```
MC_BASE_URL_CONSENTS=...
MC_BASE_URL_TXN_NOTIF=...
DATA_DIR=./data
MC_DEBUG_CONSENT_UI=1
MC_BROWSER_IP=your.public.ip.address
MC_MERCHANT_NAME=Consents Demo
```

Notes:
- `MC_ENCRYPTION_CERT_PATH` is required for 3DS start/verify authentication calls.
- `MC_BROWSER_IP` is only needed if the server sees `127.0.0.1` and the API rejects loopback IPs.
- `MC_MERCHANT_NAME` is limited to 40 characters for 3DS.

### 5) Run the app
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
