"""Filesystem JSON storage with atomic write semantics."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List

SENSITIVE_KEYS = {"pan", "full_pan", "card_number", "cvc", "cvv"}


def _data_dir(base_dir: str | Path | None = None) -> Path:
    if base_dir is not None:
        return Path(base_dir)
    return Path(os.getenv("DATA_DIR", "data"))


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _atomic_write(path: Path, payload: object) -> None:
    _ensure_dir(path.parent)
    tmp_path = path.with_suffix(path.suffix + f".tmp-{os.getpid()}")
    try:
        with tmp_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=True, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def _read_json(path: Path, default: object) -> object:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _validate_items(items: list, forbidden_keys: Iterable[str] | None = None) -> None:
    if not isinstance(items, list):
        raise ValueError("Expected a list of items")
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Expected each item to be a dict")
        if forbidden_keys:
            for key in item.keys():
                if key in forbidden_keys:
                    raise ValueError(f"Sensitive field not allowed in storage: {key}")


def read_list(filename: str, base_dir: str | Path | None = None) -> list:
    path = _data_dir(base_dir) / filename
    data = _read_json(path, default=[])
    if not isinstance(data, list):
        raise ValueError("Stored data is not a list")
    return data


def write_list(
    filename: str,
    items: list,
    base_dir: str | Path | None = None,
    forbidden_keys: Iterable[str] | None = None,
) -> None:
    if forbidden_keys is None:
        forbidden_keys = SENSITIVE_KEYS
    _validate_items(items, forbidden_keys=forbidden_keys)
    path = _data_dir(base_dir) / filename
    _atomic_write(path, items)


ENROLLMENTS_FILE = "enrollments.json"
TRANSACTIONS_FILE = "transactions.json"
NOTIFICATIONS_FILE = "notifications.json"
PENDING_ENROLLMENTS_FILE = "pending_enrollments.json"
PENDING_AUTH_FILE = "pending_authentications.json"


def load_enrollments(base_dir: str | Path | None = None) -> list:
    data = read_list(ENROLLMENTS_FILE, base_dir=base_dir)
    return _dedupe_enrollments(data)


def save_enrollments(items: list, base_dir: str | Path | None = None) -> None:
    deduped = _dedupe_enrollments(items)
    write_list(ENROLLMENTS_FILE, deduped, base_dir=base_dir, forbidden_keys=SENSITIVE_KEYS)


def _parse_created_at(value: object) -> float:
    if value in (None, ""):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return 0.0
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(text).astimezone(timezone.utc).timestamp()
        except ValueError:
            return 0.0
    return 0.0


def _find_enrollment_index(enrollments: list, record: dict) -> int | None:
    record_ref = record.get("card_reference")
    if record_ref:
        for idx, existing in enumerate(enrollments):
            if existing.get("card_reference") == record_ref:
                return idx
    record_last4 = record.get("pan_last4")
    record_alias = record.get("card_alias")
    if record_last4:
        for idx, existing in enumerate(enrollments):
            if existing.get("pan_last4") != record_last4:
                continue
            existing_alias = existing.get("card_alias")
            if record_alias and existing_alias and record_alias != existing_alias:
                continue
            return idx
    record_consent = record.get("consent_id") or record.get("id")
    if record_consent:
        for idx, existing in enumerate(enrollments):
            if existing.get("consent_id") == record_consent or existing.get("id") == record_consent:
                return idx
    return None


def _dedupe_enrollments(items: list) -> list:
    if not items:
        return items
    deduped: list = []
    for record in items:
        if not isinstance(record, dict):
            continue
        idx = _find_enrollment_index(deduped, record)
        if idx is None:
            deduped.append(record)
            continue
        existing = deduped[idx]
        record_ts = _parse_created_at(record.get("created_at"))
        existing_ts = _parse_created_at(existing.get("created_at"))
        if record_ts >= existing_ts:
            deduped[idx] = {**existing, **record}
    return deduped


def load_transactions(base_dir: str | Path | None = None) -> list:
    return read_list(TRANSACTIONS_FILE, base_dir=base_dir)


def save_transactions(items: list, base_dir: str | Path | None = None) -> None:
    write_list(TRANSACTIONS_FILE, items, base_dir=base_dir, forbidden_keys=SENSITIVE_KEYS)


def load_notifications(base_dir: str | Path | None = None) -> list:
    return read_list(NOTIFICATIONS_FILE, base_dir=base_dir)


def save_notifications(items: list, base_dir: str | Path | None = None) -> None:
    write_list(NOTIFICATIONS_FILE, items, base_dir=base_dir, forbidden_keys=SENSITIVE_KEYS)


def load_pending_enrollments(base_dir: str | Path | None = None) -> list:
    return read_list(PENDING_ENROLLMENTS_FILE, base_dir=base_dir)


def save_pending_enrollments(items: list, base_dir: str | Path | None = None) -> None:
    write_list(PENDING_ENROLLMENTS_FILE, items, base_dir=base_dir, forbidden_keys=SENSITIVE_KEYS)


def load_pending_authentications(base_dir: str | Path | None = None) -> list:
    return read_list(PENDING_AUTH_FILE, base_dir=base_dir)


def save_pending_authentications(items: list, base_dir: str | Path | None = None) -> None:
    write_list(PENDING_AUTH_FILE, items, base_dir=base_dir, forbidden_keys=SENSITIVE_KEYS)
