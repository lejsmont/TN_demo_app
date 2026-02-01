# Deployment Guide (Local Demo)

This project is intended for local sandbox demos, not production deployment.

## Local run (recommended)
1. Create/activate a virtual environment.
2. Install dependencies from `requirements.txt` and `requirements-dev.txt`.
3. Configure `.env` and place keystore/certs in `./credentials/`.
4. Start the app:
   ```bash
   python -m flask --app app run --debug
   ```
5. Open http://127.0.0.1:5000

## Environment variables
Required:
- `MC_CONSUMER_KEY`
- `MC_KEYSTORE_PASSWORD`
- `MC_KEYSTORE_PATH`
- `MC_ENCRYPTION_CERT_PATH`

Optional:
- `MC_BASE_URL_CONSENTS`
- `MC_BASE_URL_TXN_NOTIF`
- `DATA_DIR`

## Notes
- Hosted Consent UI and some sandbox flows may require manual user interaction.
- Data is stored under `./data/` by default (gitignored).
