"""Consent Management API enrollment helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .encryption import encrypt_payload_if_configured
from .mc_client import MastercardApiClient


@dataclass
class CardDetails:
    pan: str
    expiry_month: int
    expiry_year: int
    cvc: str
    cardholder_name: str


@dataclass
class EnrollmentResult:
    success: bool
    message: str
    card_reference: str | None
    consent_id: str | None
    consent_status: str | None
    auth_status: str | None
    auth_type: str | None
    auth_params: dict | None
    raw: dict | None


@dataclass
class AuthDetails:
    auth_type: str | None
    auth_status: str | None
    auth_params: dict | None


def parse_card_details(payload: Dict[str, Any]) -> CardDetails:
    required = ["pan", "expiry_month", "expiry_year", "cvc", "cardholder_name"]
    missing = [key for key in required if key not in payload or payload[key] in (None, "")]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")

    pan = str(payload["pan"]).strip()
    cvc = str(payload["cvc"]).strip()
    cardholder_name = str(payload["cardholder_name"]).strip()

    expiry_month = int(payload["expiry_month"])
    expiry_year = int(payload["expiry_year"])

    if len(pan) != 16:
        raise ValueError("PAN must be 16 digits")
    if len(cvc) != 3:
        raise ValueError("CVC must be 3 digits")
    if not (1 <= expiry_month <= 12):
        raise ValueError("expiry_month must be 1-12")
    if expiry_year < 2021:
        raise ValueError("expiry_year must be a four-digit year")
    if not cardholder_name:
        raise ValueError("cardholder_name must be provided")

    return CardDetails(
        pan=pan,
        expiry_month=expiry_month,
        expiry_year=expiry_year,
        cvc=cvc,
        cardholder_name=cardholder_name,
    )


def build_card_alias(cardholder_name: str, pan: str) -> str:
    last4 = pan[-4:]
    return f"{cardholder_name} - {last4}"


def build_consent_payload(
    card: CardDetails,
    consent_name: str,
    consent_details: Dict[str, str] | None = None,
    legal_docs: List[str] | None = None,
    device_channel: str | None = None,
    consent_duration_days: int | None = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "consents": [
            {
                "name": consent_name,
                "details": consent_details or {},
            }
        ],
        "cardDetails": {
            "pan": card.pan,
            "expiryMonth": card.expiry_month,
            "expiryYear": card.expiry_year,
            "cvc": card.cvc,
            "cardholderName": card.cardholder_name,
        },
    }
    if legal_docs:
        payload["legalDocs"] = legal_docs
    if device_channel:
        payload["deviceChannel"] = device_channel
    if consent_duration_days:
        payload["consentDurationDays"] = consent_duration_days
    return payload


def enroll_card_via_api(
    client: MastercardApiClient,
    card: CardDetails,
    consent_name: str,
    consent_details: Dict[str, str] | None = None,
    legal_docs: List[str] | None = None,
    device_channel: str | None = None,
    consent_duration_days: int | None = None,
) -> EnrollmentResult:
    payload = build_consent_payload(
        card,
        consent_name,
        consent_details=consent_details,
        legal_docs=legal_docs,
        device_channel=device_channel,
        consent_duration_days=consent_duration_days,
    )
    headers = {"Content-Type": "application/json"}
    encrypted_payload, headers = encrypt_payload_if_configured(payload, headers=headers)
    response = client.request("POST", "/consents", json_body=encrypted_payload, headers=headers, allow_retry=False)
    data = response.json()

    consents = data.get("consents") or []
    consent = consents[0] if consents else {}
    consent_id = consent.get("id")
    consent_status = consent.get("status")
    card_reference = data.get("cardReference")
    auth_status = None
    auth_type = None
    auth_params = None
    auth = data.get("auth") or {}
    if isinstance(auth, dict):
        auth_status = auth.get("status")
        auth_type = auth.get("type")
        auth_params = auth.get("params") or {}

    if not consent_id:
        return EnrollmentResult(
            success=False,
            message="Consent created but missing consent id in response",
            card_reference=card_reference,
            consent_id=None,
            consent_status=consent_status,
            auth_status=auth_status,
            auth_type=auth_type,
            auth_params=auth_params,
            raw=data,
        )

    message = f"Consent created with status {consent_status or 'UNKNOWN'}"

    return EnrollmentResult(
        success=True,
        message=message,
        card_reference=card_reference,
        consent_id=consent_id,
        consent_status=consent_status,
        auth_status=auth_status,
        auth_type=auth_type,
        auth_params=auth_params,
        raw=data,
    )


def parse_auth_details(payload: Dict[str, Any] | None) -> AuthDetails:
    auth = payload.get("auth") if payload else {}
    if not isinstance(auth, dict):
        return AuthDetails(auth_type=None, auth_status=None, auth_params=None)
    return AuthDetails(
        auth_type=auth.get("type"),
        auth_status=auth.get("status"),
        auth_params=auth.get("params") or {},
    )


def start_authentication(
    client: MastercardApiClient,
    card_reference: str,
    auth_type: str,
    auth_params: Dict[str, Any],
) -> Dict[str, Any]:
    payload = {"auth": {"type": auth_type, "params": auth_params}}
    headers = {"Content-Type": "application/json"}
    encrypted_payload, headers = encrypt_payload_if_configured(payload, headers=headers)
    response = client.request(
        "POST",
        f"/consents/{card_reference}/start-authentication",
        json_body=encrypted_payload,
        headers=headers,
        allow_retry=False,
    )
    return response.json()


def verify_authentication(
    client: MastercardApiClient,
    card_reference: str,
    auth_type: str,
    auth_params: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    payload = {"auth": {"type": auth_type, "params": auth_params or {}}}
    headers = {"Content-Type": "application/json"}
    encrypted_payload, headers = encrypt_payload_if_configured(payload, headers=headers)
    response = client.request(
        "POST",
        f"/consents/{card_reference}/verify-authentication",
        json_body=encrypted_payload,
        headers=headers,
        allow_retry=False,
    )
    return response.json()


def build_enrollment_record(result: EnrollmentResult, card: CardDetails) -> Dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    last4 = card.pan[-4:]
    return {
        "id": result.consent_id,
        "consent_id": result.consent_id,
        "card_reference": result.card_reference,
        "card_alias": build_card_alias(card.cardholder_name, card.pan),
        "pan_last4": last4,
        "status": result.consent_status,
        "auth_status": result.auth_status,
        "created_at": now,
    }
