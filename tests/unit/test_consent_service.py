from app.consent_service import CardDetails, build_consent_payload, parse_auth_details, parse_card_details


def test_parse_card_details_accepts_valid_payload():
    payload = {
        "pan": "2303779951000297",
        "expiry_month": 12,
        "expiry_year": 2027,
        "cvc": "123",
        "cardholder_name": "John",
    }
    card = parse_card_details(payload)
    assert card.pan == "2303779951000297"
    assert card.expiry_month == 12


def test_build_consent_payload():
    card = CardDetails(
        pan="2303779951000297",
        expiry_month=12,
        expiry_year=2027,
        cvc="123",
        cardholder_name="John",
    )
    payload = build_consent_payload(card, consent_name="notification")
    assert payload["cardDetails"]["pan"] == card.pan
    assert payload["consents"][0]["name"] == "notification"


def test_parse_auth_details_handles_missing_auth():
    auth = parse_auth_details({})
    assert auth.auth_type is None
    assert auth.auth_status is None
    assert auth.auth_params == {}
