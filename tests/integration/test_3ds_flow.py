from pathlib import Path

import responses

from app import storage
from app.mc_client import ClientConfig, MastercardApiClient


class DummySigner:
    def sign_request(self, uri, request):
        request.headers["Authorization"] = "OAuth dummy"
        return request


def _seed_pending_auth(tmp_path: Path, state: str, card_reference: str):
    storage.save_pending_authentications(
        [
            {
                "state": state,
                "card_reference": card_reference,
                "consent_id": "consent-3",
                "card_alias": "John - 0297",
                "pan_last4": "0297",
                "auth_type": "THREEDS",
                "auth_status": "AUTH_READY_TO_START",
                "auth_params": {
                    "threeDsMethodUrl": "https://acs.example.test",
                    "threeDSMethodNotificationURL": "https://notify.example.test",
                    "threeDSMethodData": "data",
                    "threeDSServerTransID": "trans-id",
                },
            }
        ],
        base_dir=tmp_path,
    )


def test_start_authentication_frictionless(app, client, tmp_path: Path):
    app.config["DATA_DIR"] = tmp_path
    app.config["CONSENTS_CLIENT"] = MastercardApiClient(
        config=ClientConfig(base_url="https://example.test"),
        consumer_key="ck",
        keystore_path="/tmp/none",
        keystore_password="pw",
        signer=DummySigner(),
    )

    state = "state-1"
    card_reference = "card-ref-1"
    _seed_pending_auth(tmp_path, state, card_reference)

    with responses.RequestsMock() as rsps:
        rsps.add(
            responses.POST,
            f"https://example.test/consents/{card_reference}/start-authentication",
            json={"cardReference": card_reference, "auth": {"type": "THREEDS", "status": "AUTHENTICATED"}},
            status=200,
        )
        resp = client.post(
            "/enroll/3ds/start-authentication",
            data={"state": state, "fingerprintStatus": "complete"},
        )

    assert resp.status_code == 200
    enrollments = storage.load_enrollments(base_dir=tmp_path)
    assert enrollments[0]["card_reference"] == card_reference
    pending = storage.load_pending_authentications(base_dir=tmp_path)
    assert pending == []


def test_start_authentication_challenge(app, client, tmp_path: Path):
    app.config["DATA_DIR"] = tmp_path
    app.config["CONSENTS_CLIENT"] = MastercardApiClient(
        config=ClientConfig(base_url="https://example.test"),
        consumer_key="ck",
        keystore_path="/tmp/none",
        keystore_password="pw",
        signer=DummySigner(),
    )

    state = "state-2"
    card_reference = "card-ref-2"
    _seed_pending_auth(tmp_path, state, card_reference)

    with responses.RequestsMock() as rsps:
        rsps.add(
            responses.POST,
            f"https://example.test/consents/{card_reference}/start-authentication",
            json={
                "cardReference": card_reference,
                "auth": {
                    "type": "THREEDS",
                    "status": "AUTH_IN_PROGRESS",
                    "params": {"acsUrl": "https://acs.example.test", "encodedCReq": "creq"},
                },
            },
            status=200,
        )
        resp = client.post(
            "/enroll/3ds/start-authentication",
            data={"state": state, "fingerprintStatus": "complete"},
        )

    assert resp.status_code == 200
    body = resp.data.decode("utf-8")
    assert "3DS Challenge" in body


def test_fingerprint_page_renders(app, client, tmp_path: Path):
    app.config["DATA_DIR"] = tmp_path
    state = "state-4"
    card_reference = "card-ref-4"
    _seed_pending_auth(tmp_path, state, card_reference)

    resp = client.get(f"/enroll/3ds/fingerprint?state={state}")
    assert resp.status_code == 200
    body = resp.data.decode("utf-8")
    assert "3DS Fingerprinting" in body


def test_start_authentication_missing_challenge_params(app, client, tmp_path: Path):
    app.config["DATA_DIR"] = tmp_path
    app.config["CONSENTS_CLIENT"] = MastercardApiClient(
        config=ClientConfig(base_url="https://example.test"),
        consumer_key="ck",
        keystore_path="/tmp/none",
        keystore_password="pw",
        signer=DummySigner(),
    )

    state = "state-5"
    card_reference = "card-ref-5"
    _seed_pending_auth(tmp_path, state, card_reference)

    with responses.RequestsMock() as rsps:
        rsps.add(
            responses.POST,
            f"https://example.test/consents/{card_reference}/start-authentication",
            json={
                "cardReference": card_reference,
                "auth": {"type": "THREEDS", "status": "AUTH_IN_PROGRESS", "params": {}},
            },
            status=200,
        )
        resp = client.post(
            "/enroll/3ds/start-authentication",
            data={"state": state, "fingerprintStatus": "complete"},
        )

    assert resp.status_code == 200
    assert "Challenge parameters missing" in resp.data.decode("utf-8")


def test_verify_authentication_success(app, client, tmp_path: Path):
    app.config["DATA_DIR"] = tmp_path
    app.config["CONSENTS_CLIENT"] = MastercardApiClient(
        config=ClientConfig(base_url="https://example.test"),
        consumer_key="ck",
        keystore_path="/tmp/none",
        keystore_password="pw",
        signer=DummySigner(),
    )

    state = "state-3"
    card_reference = "card-ref-3"
    _seed_pending_auth(tmp_path, state, card_reference)

    with responses.RequestsMock() as rsps:
        rsps.add(
            responses.POST,
            f"https://example.test/consents/{card_reference}/verify-authentication",
            json={
                "cardReference": card_reference,
                "auth": {"type": "THREEDS", "status": "AUTHENTICATED"},
                "consents": [{"id": "consent-3", "status": "APPROVED"}],
            },
            status=200,
        )
        resp = client.get(f"/enroll/3ds/verify?state={state}")

    assert resp.status_code == 200
    enrollments = storage.load_enrollments(base_dir=tmp_path)
    assert enrollments[0]["card_reference"] == card_reference
