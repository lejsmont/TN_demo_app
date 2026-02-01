from pathlib import Path

import pytest
import responses

from app import storage
from app.mc_client import ClientConfig, MastercardApiClient


class DummySigner:
    def sign_request(self, uri, request):
        request.headers["Authorization"] = "OAuth dummy"
        return request


def test_enroll_api_success(app, client, tmp_path: Path):
    app.config["DATA_DIR"] = tmp_path
    app.config["CONSENTS_CLIENT"] = MastercardApiClient(
        config=ClientConfig(base_url="https://example.test"),
        consumer_key="ck",
        keystore_path="/tmp/none",
        keystore_password="pw",
        signer=DummySigner(),
    )

    payload = {
        "pan": "2303779951000297",
        "expiry_month": 12,
        "expiry_year": 2027,
        "cvc": "123",
        "cardholder_name": "John",
        "consent_name": "notification",
    }

    with responses.RequestsMock() as rsps:
        rsps.add(
            responses.POST,
            "https://example.test/consents",
            json={
                "cardReference": "card-ref-1",
                "consents": [
                    {"id": "consent-1", "status": "APPROVED", "name": "notification"}
                ],
                "auth": {"status": "AUTHENTICATED"},
            },
            status=200,
        )
        resp = client.post("/enroll/api", json=payload)

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    stored = storage.load_enrollments(base_dir=tmp_path)
    assert stored[0]["consent_id"] == "consent-1"
    assert stored[0]["pan_last4"] == "0297"


def test_enroll_api_missing_fields(client):
    resp = client.post("/enroll/api", json={"pan": "123"})
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["success"] is False


def test_enroll_api_requires_3ds(app, client, tmp_path: Path):
    app.config["DATA_DIR"] = tmp_path
    app.config["CONSENTS_CLIENT"] = MastercardApiClient(
        config=ClientConfig(base_url="https://example.test"),
        consumer_key="ck",
        keystore_path="/tmp/none",
        keystore_password="pw",
        signer=DummySigner(),
    )

    payload = {
        "pan": "2303779951000297",
        "expiry_month": 12,
        "expiry_year": 2027,
        "cvc": "123",
        "cardholder_name": "John",
        "consent_name": "notification",
    }

    with responses.RequestsMock() as rsps:
        rsps.add(
            responses.POST,
            "https://example.test/consents",
            json={
                "cardReference": "card-ref-3",
                "consents": [{"id": "consent-3", "status": "REQAUTH", "name": "notification"}],
                "auth": {
                    "type": "THREEDS",
                    "status": "AUTH_READY_TO_START",
                    "params": {
                        "threeDsMethodUrl": "https://acs.example.test",
                        "threeDSMethodNotificationURL": "https://notify.example.test",
                        "threeDSMethodData": "data",
                        "threeDSServerTransID": "trans-id",
                    },
                },
            },
            status=200,
        )
        resp = client.post("/enroll/api", json=payload)

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["auth_required"] is True
    pending = storage.load_pending_authentications(base_dir=tmp_path)
    assert pending[0]["card_reference"] == "card-ref-3"
