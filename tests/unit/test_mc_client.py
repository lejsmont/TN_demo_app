import json
from pathlib import Path

import pytest
import responses

from app.mc_client import ClientConfig, MastercardApiClient, MastercardApiError, validate_env_and_keystore


class DummySigner:
    def __init__(self):
        self.calls = []

    def sign_request(self, uri, request):
        request.headers["Authorization"] = "OAuth dummy"
        self.calls.append(uri)
        return request


def test_validate_env_and_keystore_missing(monkeypatch):
    monkeypatch.delenv("MC_CONSUMER_KEY", raising=False)
    monkeypatch.delenv("MC_KEYSTORE_PASSWORD", raising=False)
    monkeypatch.delenv("MC_KEYSTORE_PATH", raising=False)

    with pytest.raises(ValueError):
        validate_env_and_keystore()


def test_validate_env_and_keystore_path_missing(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("MC_CONSUMER_KEY", "key")
    monkeypatch.setenv("MC_KEYSTORE_PASSWORD", "pass")
    missing_path = tmp_path / "missing.p12"
    monkeypatch.setenv("MC_KEYSTORE_PATH", str(missing_path))

    with pytest.raises(FileNotFoundError):
        validate_env_and_keystore()


def test_signer_adds_authorization_header():
    config = ClientConfig(base_url="https://example.test")
    client = MastercardApiClient(
        config=config,
        consumer_key="ck",
        keystore_path="/tmp/none",
        keystore_password="pw",
        signer=DummySigner(),
    )

    with responses.RequestsMock() as rsps:
        rsps.add(responses.GET, "https://example.test/ping", json={"ok": True}, status=200)
        resp = client.request("GET", "/ping", allow_retry=False)

    assert resp.status_code == 200
    assert resp.request.headers.get("Authorization") == "OAuth dummy"


def test_error_mapping_from_response():
    config = ClientConfig(base_url="https://example.test")
    client = MastercardApiClient(
        config=config,
        consumer_key="ck",
        keystore_path="/tmp/none",
        keystore_password="pw",
        signer=DummySigner(),
    )

    with responses.RequestsMock() as rsps:
        payload = {"ReasonCode": "INVALID", "Description": "Bad"}
        rsps.add(responses.GET, "https://example.test/fail", json=payload, status=400)
        with pytest.raises(MastercardApiError) as excinfo:
            client.request("GET", "/fail", allow_retry=False)

    err = excinfo.value
    assert err.status_code == 400
    assert err.reason_code == "INVALID"
    assert err.description == "Bad"


def test_retry_on_server_error():
    config = ClientConfig(base_url="https://example.test", max_retries=3, backoff_seconds=0)
    client = MastercardApiClient(
        config=config,
        consumer_key="ck",
        keystore_path="/tmp/none",
        keystore_password="pw",
        signer=DummySigner(),
    )

    with responses.RequestsMock() as rsps:
        rsps.add(responses.GET, "https://example.test/retry", status=500, json={"error": True})
        rsps.add(responses.GET, "https://example.test/retry", status=500, json={"error": True})
        rsps.add(responses.GET, "https://example.test/retry", status=200, json={"ok": True})
        resp = client.request("GET", "/retry")

    assert resp.status_code == 200
