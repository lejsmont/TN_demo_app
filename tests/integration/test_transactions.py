from pathlib import Path

import responses

from app import storage
from app.mc_client import ClientConfig, MastercardApiClient


class DummySigner:
    def sign_request(self, uri, request):
        request.headers["Authorization"] = "OAuth dummy"
        return request


def test_post_transaction_success(app, client, tmp_path: Path):
    app.config["DATA_DIR"] = tmp_path
    app.config["TXN_CLIENT"] = MastercardApiClient(
        config=ClientConfig(base_url="https://example.test"),
        consumer_key="ck",
        keystore_path="/tmp/none",
        keystore_password="pw",
        signer=DummySigner(),
    )

    payload = {
        "consent_id": "card-ref-1",
        "amount": "12.34",
        "currency": "USD",
        "merchant": "Demo Store",
    }

    with responses.RequestsMock() as rsps:
        rsps.add(
            responses.POST,
            "https://example.test/notifications/transactions",
            json={},
            status=200,
        )
        resp = client.post("/transactions", data=payload)

    assert resp.status_code == 200
    stored = storage.load_transactions(base_dir=tmp_path)
    assert stored[0]["card_reference"] == "card-ref-1"
    assert stored[0]["status"] == "POSTED"
    assert stored[0]["reference_number"]
    assert stored[0]["system_trace_audit_number"]


def test_post_transaction_missing_fields(client):
    resp = client.post("/transactions", data={"amount": "1"})
    assert resp.status_code == 400


def test_post_transaction_json_success(app, client, tmp_path: Path):
    app.config["DATA_DIR"] = tmp_path
    app.config["TXN_CLIENT"] = MastercardApiClient(
        config=ClientConfig(base_url="https://example.test"),
        consumer_key="ck",
        keystore_path="/tmp/none",
        keystore_password="pw",
        signer=DummySigner(),
    )

    payload = {
        "card_reference": "card-ref-2",
        "amount": "9.99",
        "currency": "USD",
        "merchant": "Demo Shop",
    }

    with responses.RequestsMock() as rsps:
        rsps.add(
            responses.POST,
            "https://example.test/notifications/transactions",
            json={},
            status=200,
        )
        resp = client.post("/transactions", json=payload)

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True


def test_post_transaction_json_missing_fields(client):
    resp = client.post("/transactions", json={"amount": 1})
    assert resp.status_code == 400
