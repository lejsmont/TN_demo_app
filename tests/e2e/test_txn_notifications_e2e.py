import os
import time
from datetime import datetime

import pytest

from app.config import load_env
from app.consent_service import CardDetails, build_consent_payload
from app.encryption import encrypt_payload_if_configured
from app.mc_client import MastercardApiClient, MastercardApiError, validate_env_and_keystore
from app.notification_service import build_notification_record, poll_undelivered_notifications
from app.transaction_service import (
    TransactionInput,
    build_transaction_payload,
    generate_transaction_identifiers,
)


pytestmark = pytest.mark.e2e


def _require_e2e_enabled():
    if os.getenv("RUN_E2E") != "1":
        pytest.skip("RUN_E2E is not set to 1")

    load_env()
    if not os.getenv("MC_ENCRYPTION_CERT_PATH"):
        pytest.skip("MC_ENCRYPTION_CERT_PATH is not set (payload encryption required for consent)")
    try:
        validate_env_and_keystore()
    except (ValueError, FileNotFoundError) as exc:
        pytest.skip(str(exc))


def _create_test_consent() -> str:
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
    card_reference = data.get("cardReference")
    if not card_reference:
        pytest.fail("Consent API did not return cardReference")
    return card_reference


def test_transaction_notifications_e2e():
    _require_e2e_enabled()

    card_reference = _create_test_consent()
    base_url = os.getenv("MC_BASE_URL_TXN_NOTIF", "https://sandbox.api.mastercard.com/openapis")
    client = MastercardApiClient.from_env(base_url)

    identifiers = generate_transaction_identifiers()
    txn = TransactionInput(
        card_reference=card_reference,
        amount=12.34,
        currency="USD",
        merchant_name="Codex Demo",
    )
    payload = build_transaction_payload(
        txn,
        reference_number=identifiers.reference_number,
        system_trace_audit_number=identifiers.system_trace_audit_number,
    )
    headers = {"Content-Type": "application/json"}
    start_time = time.time()

    try:
        client.request("POST", "/notifications/transactions", json_body=payload, headers=headers, allow_retry=False)
    except MastercardApiError as exc:
        pytest.fail(
            "Transaction Notifications API error: "
            f"{exc} (reason={exc.reason_code}, correlation={exc.correlation_id})"
        )

    try:
        result = poll_undelivered_notifications(
            client,
            card_reference=None,
            max_attempts=5,
            backoff_seconds=2.0,
        )
    except MastercardApiError as exc:
        pytest.fail(
            "Undelivered Notifications API error: "
            f"{exc} (reason={exc.reason_code}, correlation={exc.correlation_id})"
        )

    records = [build_notification_record(item) for item in result.notifications]

    def _parse_time(value):
        if not value:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value).strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        if len(text) >= 5 and text[-5] in "+-" and text[-2:].isdigit() and text[-4:-2].isdigit():
            if text[-3] != ":":
                text = text[:-2] + ":" + text[-2:]
        try:
            return datetime.fromisoformat(text).timestamp()
        except ValueError:
            return None

    def _norm(value):
        return str(value).strip().upper() if value not in (None, "") else ""

    match = next(
        (
            record
            for record in records
            if record.get("card_reference") == card_reference
            and _norm(record.get("merchant")) == "CODEX DEMO"
            and str(record.get("amount")) in {"12.34", "12.340", "12.3400"}
            and _norm(record.get("currency")) == "USD"
            and (_parse_time(record.get("event_time") or record.get("received_at")) or 0) >= start_time - 120
        ),
        None,
    )
    if not match:
        pytest.fail(
            "No undelivered notification matched the posted transaction details "
            "(card_reference, merchant, amount, currency) after the post request."
        )

    assert match.get("card_reference") == card_reference
