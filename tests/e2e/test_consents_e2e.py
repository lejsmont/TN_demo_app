import os

import pytest

from app.config import load_env
from app.consent_service import CardDetails, build_consent_payload
from app.encryption import encrypt_payload_if_configured
from app.mc_client import MastercardApiClient, MastercardApiError, validate_env_and_keystore


pytestmark = pytest.mark.e2e


def _require_e2e_enabled():
    if os.getenv("RUN_E2E") != "1":
        pytest.skip("RUN_E2E is not set to 1")

    load_env()
    if not os.getenv("MC_ENCRYPTION_CERT_PATH"):
        pytest.skip("MC_ENCRYPTION_CERT_PATH is not set (payload encryption required)")
    try:
        validate_env_and_keystore()
    except (ValueError, FileNotFoundError) as exc:
        pytest.skip(str(exc))


def test_consents_create_e2e():
    _require_e2e_enabled()

    base_url = os.getenv("MC_BASE_URL_CONSENTS", "https://sandbox.api.mastercard.com/openapis/authentication")
    client = MastercardApiClient.from_env(base_url)

    card = CardDetails(
        pan="2303779951000297",
        expiry_month=12,
        expiry_year=2027,
        cvc="123",
        cardholder_name="John",
    )

    payload = build_consent_payload(card, consent_name="notification")
    headers = {"Content-Type": "application/json"}
    encrypted_payload, headers = encrypt_payload_if_configured(payload, headers=headers)

    try:
        response = client.request("POST", "/consents", json_body=encrypted_payload, headers=headers, allow_retry=False)
    except MastercardApiError as exc:
        pytest.fail(f"Consent API error: {exc} (reason={exc.reason_code}, correlation={exc.correlation_id})")

    data = response.json()
    assert data.get("cardReference")
    consents = data.get("consents") or []
    assert consents and consents[0].get("id")
