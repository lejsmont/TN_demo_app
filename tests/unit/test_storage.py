from pathlib import Path

import pytest

from app import storage


def test_read_list_returns_empty_when_missing(tmp_path: Path):
    data = storage.read_list("missing.json", base_dir=tmp_path)
    assert data == []


def test_write_and_read_list_roundtrip(tmp_path: Path):
    items = [{"id": "1", "status": "ok"}]
    storage.write_list("items.json", items, base_dir=tmp_path)
    assert storage.read_list("items.json", base_dir=tmp_path) == items


def test_write_list_enforces_dict_items(tmp_path: Path):
    with pytest.raises(ValueError):
        storage.write_list("items.json", ["not-a-dict"], base_dir=tmp_path)


def test_write_list_blocks_sensitive_keys(tmp_path: Path):
    with pytest.raises(ValueError):
        storage.write_list("items.json", [{"pan": "5555"}], base_dir=tmp_path)


def test_atomic_write_has_no_tmp_leftover(tmp_path: Path):
    items = [{"id": "1"}]
    storage.write_list("items.json", items, base_dir=tmp_path)
    tmp_files = list(tmp_path.glob("*.tmp-*"))
    assert tmp_files == []


def test_dataset_helpers_use_expected_files(tmp_path: Path):
    storage.save_enrollments([{"id": "e1"}], base_dir=tmp_path)
    assert (tmp_path / storage.ENROLLMENTS_FILE).exists()
    storage.save_transactions([{"id": "t1"}], base_dir=tmp_path)
    assert (tmp_path / storage.TRANSACTIONS_FILE).exists()
    storage.save_notifications([{"id": "n1"}], base_dir=tmp_path)
    assert (tmp_path / storage.NOTIFICATIONS_FILE).exists()
    storage.save_pending_enrollments([{"id": "p1"}], base_dir=tmp_path)
    assert (tmp_path / storage.PENDING_ENROLLMENTS_FILE).exists()


def test_load_enrollments_deduplicates(tmp_path: Path):
    items = [
        {
            "card_reference": "ref-1",
            "pan_last4": "0297",
            "card_alias": "John - 0297",
            "status": "APPROVED",
            "created_at": "2026-02-01T00:00:00+00:00",
        },
        {
            "card_reference": "ref-1",
            "pan_last4": "0297",
            "card_alias": "John - 0297",
            "status": "EXPIRED",
            "created_at": "2026-02-02T00:00:00+00:00",
        },
    ]
    storage.save_enrollments(items, base_dir=tmp_path)
    deduped = storage.load_enrollments(base_dir=tmp_path)
    assert len(deduped) == 1
    assert deduped[0]["status"] == "EXPIRED"
    raw = storage.read_list(storage.ENROLLMENTS_FILE, base_dir=tmp_path)
    assert len(raw) == 1
