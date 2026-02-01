"""Undelivered notifications polling and reconciliation helpers."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from uuid import uuid4
import json

from .mc_client import MastercardApiClient

SENSITIVE_FIELDS = {"pan", "full_pan", "card_number", "cvc", "cvv"}
MERCHANT_KEYS = ("merchantName", "merchant_name", "merchant", "merchant_name", "merchantNameLocation")
EVENT_TIME_KEYS = (
    "eventTime",
    "event_time",
    "transactionDate",
    "transactionTime",
    "transactionTimestamp",
    "timestamp",
    "systemDateTime",
    "createdAt",
    "created_at",
)
REFERENCE_NUMBER_KEYS = ("referenceNumber", "reference_number")
SYSTEM_TRACE_KEYS = ("systemTraceAuditNumber", "system_trace_audit_number", "stan")
TRANS_UID_KEYS = ("transUid", "trans_uid")
SEQUENCE_KEYS = ("notificationSequenceId", "notification_sequence_id")
MESSAGE_TYPE_KEYS = ("messageType", "message_type")


@dataclass
class PollResult:
    notifications: list
    attempts: int
    found: bool
    message: str
    matched: dict | None = None


def _strip_sensitive(payload: object) -> object:
    if isinstance(payload, dict):
        cleaned = {}
        for key, value in payload.items():
            if key in SENSITIVE_FIELDS:
                continue
            cleaned[key] = _strip_sensitive(value)
        return cleaned
    if isinstance(payload, list):
        return [_strip_sensitive(item) for item in payload]
    return payload


def _maybe_parse_json(value: object) -> object | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text or (not text.startswith("{") and not text.startswith("[")):
        return None
    try:
        return json.loads(text)
    except (TypeError, json.JSONDecodeError):
        return None


def _extract_notifications(payload: object) -> list:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("notifications", "notification", "data", "items"):
            if key not in payload:
                continue
            value = payload[key]
            if isinstance(value, list):
                return value
            if isinstance(value, dict):
                nested = _extract_notifications(value)
                return nested if nested else [value]
            return [value]
        if "payload" in payload:
            parsed = _maybe_parse_json(payload.get("payload"))
            if parsed is not None:
                nested = _extract_notifications(parsed)
                return nested if nested else [parsed]
    return []


def _extract_card_reference(payload: object) -> str | None:
    if isinstance(payload, dict):
        for key in ("cardReference", "card_reference"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value
        for value in payload.values():
            parsed = _maybe_parse_json(value)
            if parsed is not None:
                found = _extract_card_reference(parsed)
                if found:
                    return found
            found = _extract_card_reference(value)
            if found:
                return found
    elif isinstance(payload, list):
        for item in payload:
            parsed = _maybe_parse_json(item)
            if parsed is not None:
                found = _extract_card_reference(parsed)
                if found:
                    return found
            found = _extract_card_reference(item)
            if found:
                return found
    return None


def _extract_value(payload: object, keys: tuple[str, ...]) -> object | None:
    if isinstance(payload, dict):
        for key in keys:
            if key in payload and payload[key] not in (None, ""):
                return payload[key]
        for value in payload.values():
            parsed = _maybe_parse_json(value)
            if parsed is not None:
                found = _extract_value(parsed, keys)
                if found not in (None, ""):
                    return found
            found = _extract_value(value, keys)
            if found not in (None, ""):
                return found
    elif isinstance(payload, list):
        for item in payload:
            parsed = _maybe_parse_json(item)
            if parsed is not None:
                found = _extract_value(parsed, keys)
                if found not in (None, ""):
                    return found
            found = _extract_value(item, keys)
            if found not in (None, ""):
                return found
    return None


def _extract_amount_currency(payload: object) -> tuple[object | None, object | None]:
    amount_keys = (
        "cardholderAmount",
        "cardHolderAmount",
        "cardholder_amount",
        "transactionAmount",
        "transaction_amount",
        "amount",
        "merchantAmount",
        "merchant_amount",
    )
    currency_keys = (
        "cardholderCurrency",
        "cardHolderCurrency",
        "cardholder_currency",
        "transactionCurrency",
        "transaction_currency",
        "currency",
        "merchantCurrency",
        "merchant_currency",
        "currencyCode",
        "currency_code",
    )
    if isinstance(payload, dict):
        for key in amount_keys:
            value = payload.get(key)
            if isinstance(value, dict):
                amount = value.get("amount") or value.get("value") or value.get("amountValue")
                currency = value.get("currency") or value.get("currencyCode")
                if amount not in (None, "") or currency not in (None, ""):
                    return amount, currency
            if value not in (None, "") and not isinstance(value, (dict, list)):
                amount = value
                currency = _extract_value(payload, currency_keys)
                return amount, currency
        for value in payload.values():
            parsed = _maybe_parse_json(value)
            if parsed is not None:
                amount, currency = _extract_amount_currency(parsed)
                if amount not in (None, "") or currency not in (None, ""):
                    return amount, currency
            amount, currency = _extract_amount_currency(value)
            if amount not in (None, "") or currency not in (None, ""):
                return amount, currency
    elif isinstance(payload, list):
        for item in payload:
            parsed = _maybe_parse_json(item)
            if parsed is not None:
                amount, currency = _extract_amount_currency(parsed)
                if amount not in (None, "") or currency not in (None, ""):
                    return amount, currency
            amount, currency = _extract_amount_currency(item)
            if amount not in (None, "") or currency not in (None, ""):
                return amount, currency
    return None, None


def _has_encrypted_payload(payload: object) -> bool:
    if isinstance(payload, dict):
        if "encryptedValue" in payload or "jweEncryptedData" in payload:
            return True
        for value in payload.values():
            parsed = _maybe_parse_json(value)
            if parsed is not None and _has_encrypted_payload(parsed):
                return True
            if _has_encrypted_payload(value):
                return True
    elif isinstance(payload, list):
        for item in payload:
            parsed = _maybe_parse_json(item)
            if parsed is not None and _has_encrypted_payload(parsed):
                return True
            if _has_encrypted_payload(item):
                return True
    return False


def _normalize_amount(value: object) -> str | None:
    if value in (None, ""):
        return None
    try:
        return str(Decimal(str(value)).normalize())
    except (InvalidOperation, ValueError):
        return str(value).strip()


def _normalize_text(value: object) -> str | None:
    if value in (None, ""):
        return None
    return str(value).strip().upper()


def notification_fingerprint(record: dict) -> str | None:
    trans_uid = record.get("trans_uid")
    if trans_uid not in (None, ""):
        return f"trans_uid:{trans_uid}"

    sequence_id = record.get("notification_sequence_id")
    if sequence_id not in (None, ""):
        return f"sequence:{sequence_id}"

    card_reference = record.get("card_reference") or record.get("consent_id")
    if card_reference in (None, ""):
        return None

    reference_number = record.get("reference_number")
    system_trace = record.get("system_trace_audit_number")
    amount = record.get("amount")
    currency = record.get("currency")
    merchant = record.get("merchant")
    event_time = record.get("event_time") or record.get("received_at") or record.get("created_at")
    message_type = record.get("message_type")

    normalized_amount = _normalize_amount(amount)
    normalized_currency = _normalize_text(currency)
    normalized_merchant = _normalize_text(merchant)
    normalized_message_type = _normalize_text(message_type)
    normalized_reference = _normalize_text(reference_number)
    normalized_system_trace = _normalize_text(system_trace)

    parts = [
        str(card_reference).strip(),
        normalized_reference or "",
        normalized_system_trace or "",
        normalized_amount or "",
        normalized_currency or "",
        normalized_merchant or "",
        str(event_time).strip() if event_time not in (None, "") else "",
        normalized_message_type or "",
    ]
    if not any(parts[1:]):
        return None
    return "combo:" + "|".join(parts)


def ensure_notification_fingerprint(record: dict) -> str | None:
    fingerprint = record.get("fingerprint")
    if fingerprint not in (None, ""):
        return fingerprint
    fingerprint = notification_fingerprint(record)
    if fingerprint:
        record["fingerprint"] = fingerprint
    return fingerprint


def enrich_notification_record(record: dict) -> bool:
    payload = record.get("payload")
    if payload is None:
        return False

    parsed = _maybe_parse_json(payload)
    payload_obj = parsed if parsed is not None else payload
    changed = False

    if not record.get("card_reference"):
        card_reference = _extract_card_reference(payload_obj)
        if card_reference:
            record["card_reference"] = card_reference
            changed = True

    if not record.get("merchant"):
        merchant = _extract_value(payload_obj, MERCHANT_KEYS)
        if merchant not in (None, ""):
            record["merchant"] = merchant
            changed = True

    amount, currency = None, None
    if not record.get("amount") or not record.get("currency"):
        amount, currency = _extract_amount_currency(payload_obj)

    if not record.get("amount") and amount not in (None, ""):
        record["amount"] = amount
        changed = True

    if not record.get("currency") and currency not in (None, ""):
        record["currency"] = currency
        changed = True

    if not record.get("event_time"):
        event_time = _extract_value(payload_obj, EVENT_TIME_KEYS)
        if event_time not in (None, ""):
            record["event_time"] = event_time
            changed = True

    if not record.get("reference_number"):
        reference_number = _extract_value(payload_obj, REFERENCE_NUMBER_KEYS)
        if reference_number not in (None, ""):
            record["reference_number"] = reference_number
            changed = True

    if not record.get("system_trace_audit_number"):
        system_trace_audit_number = _extract_value(payload_obj, SYSTEM_TRACE_KEYS)
        if system_trace_audit_number not in (None, ""):
            record["system_trace_audit_number"] = system_trace_audit_number
            changed = True

    if not record.get("trans_uid"):
        trans_uid = _extract_value(payload_obj, TRANS_UID_KEYS)
        if trans_uid not in (None, ""):
            record["trans_uid"] = trans_uid
            changed = True

    if not record.get("notification_sequence_id"):
        sequence_id = _extract_value(payload_obj, SEQUENCE_KEYS)
        if sequence_id not in (None, ""):
            record["notification_sequence_id"] = sequence_id
            changed = True

    if not record.get("message_type"):
        message_type = _extract_value(payload_obj, MESSAGE_TYPE_KEYS)
        if message_type not in (None, ""):
            record["message_type"] = message_type
            changed = True

    if "encrypted_payload" not in record:
        record["encrypted_payload"] = _has_encrypted_payload(payload_obj)
        changed = True

    if not record.get("fingerprint"):
        if ensure_notification_fingerprint(record):
            changed = True

    return changed


def build_notification_record(notification: dict) -> dict:
    card_reference = _extract_card_reference(notification)
    merchant = _extract_value(notification, MERCHANT_KEYS)
    amount, currency = _extract_amount_currency(notification)
    event_time = _extract_value(notification, EVENT_TIME_KEYS)
    reference_number = _extract_value(notification, REFERENCE_NUMBER_KEYS)
    system_trace_audit_number = _extract_value(notification, SYSTEM_TRACE_KEYS)
    trans_uid = _extract_value(notification, TRANS_UID_KEYS)
    notification_sequence_id = _extract_value(notification, SEQUENCE_KEYS)
    message_type = _extract_value(notification, MESSAGE_TYPE_KEYS)
    payload = _strip_sensitive(notification)
    encrypted_payload = _has_encrypted_payload(notification)
    record = {
        "id": notification.get("id") or notification.get("notificationId") or str(uuid4()),
        "card_reference": card_reference,
        "merchant": merchant,
        "amount": amount,
        "currency": currency,
        "event_time": event_time,
        "reference_number": reference_number,
        "system_trace_audit_number": system_trace_audit_number,
        "trans_uid": trans_uid,
        "notification_sequence_id": notification_sequence_id,
        "message_type": message_type,
        "encrypted_payload": encrypted_payload,
        "status": "UNDELIVERED",
        "received_at": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }
    ensure_notification_fingerprint(record)
    return record


def fetch_undelivered_notifications(client: MastercardApiClient, after: int | None = None) -> list:
    params = {"after": after} if after is not None else None
    response = client.request(
        "GET",
        "/notifications/undelivered-notifications",
        params=params,
        headers={"Content-Type": "application/json"},
    )
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    return _extract_notifications(payload)


def poll_undelivered_notifications(
    client: MastercardApiClient,
    *,
    card_reference: str | None = None,
    after: int | None = None,
    max_attempts: int = 3,
    backoff_seconds: float = 1.0,
    sleep_fn=time.sleep,
) -> PollResult:
    collected: list = []
    matched: dict | None = None

    for attempt in range(1, max_attempts + 1):
        notifications = fetch_undelivered_notifications(client, after=after)
        collected.extend(notifications)

        if card_reference:
            for notification in notifications:
                if _extract_card_reference(notification) == card_reference:
                    matched = notification
                    break
        if matched:
            break

        if attempt < max_attempts:
            sleep_fn(backoff_seconds * (2 ** (attempt - 1)))

    if card_reference:
        if matched:
            message = f"Found undelivered notification for card reference {card_reference}"
            found = True
        else:
            message = (
                f"No undelivered notifications found for card reference {card_reference} "
                f"after {max_attempts} attempts"
            )
            found = False
    else:
        message = f"Fetched {len(collected)} undelivered notifications"
        found = False

    return PollResult(
        notifications=collected,
        attempts=max_attempts,
        found=found,
        message=message,
        matched=matched,
    )
