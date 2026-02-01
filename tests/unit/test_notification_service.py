from app.notification_service import (
    _extract_amount_currency,
    _extract_card_reference,
    _extract_notifications,
    _extract_value,
    _has_encrypted_payload,
    _strip_sensitive,
    enrich_notification_record,
    notification_fingerprint,
    poll_undelivered_notifications,
)


class DummyResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class DummyClient:
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.calls = 0

    def request(self, *_args, **_kwargs):
        payload = self.payloads[min(self.calls, len(self.payloads) - 1)]
        self.calls += 1
        return DummyResponse(payload)


def test_strip_sensitive_removes_pan():
    payload = {"pan": "123", "nested": {"cardReference": "ref"}}
    cleaned = _strip_sensitive(payload)
    assert "pan" not in cleaned
    assert cleaned["nested"]["cardReference"] == "ref"


def test_extract_notifications_from_wrapped_payload():
    payload = {"notifications": [{"cardReference": "ref-1"}]}
    notifications = _extract_notifications(payload)
    assert notifications[0]["cardReference"] == "ref-1"


def test_extract_card_reference_nested():
    payload = {"data": {"cardReference": "ref-2"}}
    assert _extract_card_reference(payload) == "ref-2"


def test_poll_undelivered_backoff_and_match():
    payloads = [
        {"notifications": []},
        {"notifications": [{"cardReference": "match-1"}]},
    ]
    client = DummyClient(payloads)
    sleeps = []

    def fake_sleep(duration):
        sleeps.append(duration)

    result = poll_undelivered_notifications(
        client,
        card_reference="match-1",
        max_attempts=3,
        backoff_seconds=1.0,
        sleep_fn=fake_sleep,
    )

    assert result.found is True
    assert sleeps == [1.0]


def test_extract_amount_currency_from_json_string():
    payload = {"payload": "{\"merchantAmount\":12.5,\"merchantCurrency\":\"USD\"}"}
    amount, currency = _extract_amount_currency(payload)
    assert amount == 12.5
    assert currency == "USD"


def test_extract_amount_currency_from_direct_keys():
    payload = {"merchantAmount": 9.99, "merchantCurrency": "EUR"}
    amount, currency = _extract_amount_currency(payload)
    assert amount == 9.99
    assert currency == "EUR"


def test_extract_value_from_json_string():
    payload = {"payload": "{\"merchantName\":\"Demo Store\"}"}
    value = _extract_value(payload, ("merchantName",))
    assert value == "Demo Store"


def test_has_encrypted_payload_detects_nested():
    payload = {"payload": "{\"encryptedValue\":\"abc\"}"}
    assert _has_encrypted_payload(payload) is True


def test_notification_fingerprint_prefers_trans_uid():
    record = {
        "card_reference": "card-1",
        "trans_uid": "TRANS-123",
        "reference_number": "999999999",
    }
    assert record.get("fingerprint") is None
    assert notification_fingerprint(record) == "trans_uid:TRANS-123"


def test_enrich_notification_record_from_payload():
    record = {
        "id": "note-1",
        "payload": {
            "cardReference": "card-1",
            "merchantName": "Demo Store",
            "merchantAmount": 12.5,
            "merchantCurrency": "USD",
            "referenceNumber": "123456789",
            "systemTraceAuditNumber": "123456",
        },
    }
    changed = enrich_notification_record(record)
    assert changed is True
    assert record["card_reference"] == "card-1"
    assert record["merchant"] == "Demo Store"
    assert record["amount"] == 12.5
    assert record["currency"] == "USD"
    assert record["reference_number"] == "123456789"
    assert record["system_trace_audit_number"] == "123456"
    assert record["fingerprint"]
