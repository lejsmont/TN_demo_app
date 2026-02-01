"""Transaction Notifications helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import secrets
from uuid import uuid4

from .mc_client import MastercardApiClient


@dataclass
class TransactionInput:
    card_reference: str
    amount: Decimal
    currency: str
    merchant_name: str


@dataclass
class TransactionResult:
    success: bool
    message: str
    correlation_id: str | None


@dataclass
class TransactionIdentifiers:
    reference_number: str
    system_trace_audit_number: str


def _random_numeric(length: int) -> str:
    return "".join(str(secrets.randbelow(10)) for _ in range(length))


def generate_transaction_identifiers() -> TransactionIdentifiers:
    return TransactionIdentifiers(
        reference_number=_random_numeric(9),
        system_trace_audit_number=_random_numeric(6),
    )


def parse_transaction_input(payload: dict) -> TransactionInput:
    card_reference = payload.get("card_reference") or payload.get("consent_id")
    if not card_reference:
        raise ValueError("Missing card reference")

    merchant_name = payload.get("merchant") or payload.get("merchant_name")
    if not merchant_name:
        raise ValueError("Missing merchant name")

    amount_raw = payload.get("amount")
    if amount_raw in (None, ""):
        raise ValueError("Missing amount")

    try:
        amount = Decimal(str(amount_raw))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Invalid amount") from exc

    if amount <= 0:
        raise ValueError("Amount must be greater than zero")

    currency = str(payload.get("currency") or payload.get("cardholder_currency") or "").strip().upper()
    if len(currency) != 3 or not currency.isalpha():
        raise ValueError("Currency must be a 3-letter code")

    return TransactionInput(
        card_reference=str(card_reference).strip(),
        amount=amount,
        currency=currency,
        merchant_name=str(merchant_name).strip(),
    )


def build_transaction_payload(
    txn: TransactionInput,
    *,
    reference_number: str | None = None,
    system_trace_audit_number: str | None = None,
) -> dict:
    payload = {
        "cardReference": txn.card_reference,
        "cardholderAmount": float(txn.amount),
        "cardholderCurrency": txn.currency,
        "merchantName": txn.merchant_name,
    }
    if reference_number:
        payload["referenceNumber"] = reference_number
    if system_trace_audit_number:
        payload["systemTraceAuditNumber"] = system_trace_audit_number
    return payload


def build_transaction_record(
    txn: TransactionInput,
    status: str,
    correlation_id: str | None = None,
    consent_id: str | None = None,
    card_alias: str | None = None,
    error: str | None = None,
    reference_number: str | None = None,
    system_trace_audit_number: str | None = None,
) -> dict:
    return {
        "id": str(uuid4()),
        "consent_id": consent_id,
        "card_reference": txn.card_reference,
        "card_alias": card_alias,
        "amount": str(txn.amount),
        "currency": txn.currency,
        "merchant": txn.merchant_name,
        "status": status,
        "posted_at": datetime.now(timezone.utc).isoformat(),
        "correlation_id": correlation_id,
        "error": error,
        "reference_number": reference_number,
        "system_trace_audit_number": system_trace_audit_number,
        "source": "ui",
    }


def post_transaction(
    client: MastercardApiClient,
    txn: TransactionInput,
    *,
    reference_number: str | None = None,
    system_trace_audit_number: str | None = None,
) -> TransactionResult:
    payload = build_transaction_payload(
        txn,
        reference_number=reference_number,
        system_trace_audit_number=system_trace_audit_number,
    )
    headers = {"Content-Type": "application/json"}
    response = client.request(
        "POST",
        "/notifications/transactions",
        json_body=payload,
        headers=headers,
        allow_retry=False,
    )
    correlation_id = response.headers.get("Correlation-Id") or response.headers.get("X-Correlation-ID")
    return TransactionResult(success=True, message="Transaction posted", correlation_id=correlation_id)
