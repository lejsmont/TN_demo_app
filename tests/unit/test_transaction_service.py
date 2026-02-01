import pytest

from app.transaction_service import (
    build_transaction_payload,
    generate_transaction_identifiers,
    parse_transaction_input,
)


def test_parse_transaction_input_success():
    payload = {
        "card_reference": "ref-1",
        "amount": "10.50",
        "currency": "usd",
        "merchant": "Coffee Shop",
    }
    txn = parse_transaction_input(payload)
    assert txn.card_reference == "ref-1"
    assert txn.currency == "USD"


def test_parse_transaction_input_missing():
    with pytest.raises(ValueError):
        parse_transaction_input({})


def test_parse_transaction_input_invalid_amount():
    with pytest.raises(ValueError):
        parse_transaction_input(
            {"card_reference": "ref-1", "amount": "-1", "currency": "USD", "merchant": "Shop"}
        )


def test_build_transaction_payload():
    txn = parse_transaction_input(
        {"card_reference": "ref-1", "amount": "12.34", "currency": "USD", "merchant": "Shop"}
    )
    payload = build_transaction_payload(
        txn,
        reference_number="123456789",
        system_trace_audit_number="654321",
    )
    assert payload["cardReference"] == "ref-1"
    assert payload["cardholderCurrency"] == "USD"
    assert payload["referenceNumber"] == "123456789"
    assert payload["systemTraceAuditNumber"] == "654321"


def test_generate_transaction_identifiers():
    identifiers = generate_transaction_identifiers()
    assert identifiers.reference_number.isdigit()
    assert identifiers.system_trace_audit_number.isdigit()
    assert len(identifiers.reference_number) == 9
    assert len(identifiers.system_trace_audit_number) == 6
