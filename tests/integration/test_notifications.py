from pathlib import Path

import responses

from app import storage
from app.mc_client import ClientConfig, MastercardApiClient


class DummySigner:
    def sign_request(self, uri, request):
        request.headers["Authorization"] = "OAuth dummy"
        return request


def test_get_undelivered_notifications(app, client, tmp_path: Path):
    app.config["DATA_DIR"] = tmp_path
    app.config["TXN_CLIENT"] = MastercardApiClient(
        config=ClientConfig(base_url="https://example.test"),
        consumer_key="ck",
        keystore_path="/tmp/none",
        keystore_password="pw",
        signer=DummySigner(),
    )

    payload = {"notifications": [{"cardReference": "card-1", "id": "note-1"}]}

    with responses.RequestsMock() as rsps:
        rsps.add(
            responses.GET,
            "https://example.test/notifications/undelivered-notifications",
            json=payload,
            status=200,
        )
        resp = client.get("/notifications/undelivered?card_reference=card-1")

    assert resp.status_code == 200
    stored = storage.load_notifications(base_dir=tmp_path)
    assert stored[0]["card_reference"] == "card-1"


def test_get_undelivered_notifications_not_found(app, client, tmp_path: Path):
    app.config["DATA_DIR"] = tmp_path
    app.config["TXN_CLIENT"] = MastercardApiClient(
        config=ClientConfig(base_url="https://example.test"),
        consumer_key="ck",
        keystore_path="/tmp/none",
        keystore_password="pw",
        signer=DummySigner(),
    )

    payload = {"notifications": []}

    with responses.RequestsMock() as rsps:
        rsps.add(
            responses.GET,
            "https://example.test/notifications/undelivered-notifications",
            json=payload,
            status=200,
        )
        resp = client.get("/notifications/undelivered?card_reference=missing")

    assert resp.status_code == 404
