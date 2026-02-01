from datetime import datetime, timezone
from pathlib import Path

import jwt

from app import storage


def test_enroll_ui_start_creates_pending(app, client, tmp_path: Path):
    app.config["DATA_DIR"] = tmp_path
    app.config["CONSENT_UI_JWT"] = "dummy.jwt"
    app.config["CONSENT_UI_SRC"] = "https://consents.mastercard.com"

    resp = client.get("/enroll/ui/start")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "iframe" in html

    pending = storage.load_pending_enrollments(base_dir=tmp_path)
    assert len(pending) == 1
    assert pending[0]["state"]


def test_enroll_ui_frame_renders_consent_ui(app, client, tmp_path: Path):
    app.config["DATA_DIR"] = tmp_path
    app.config["CONSENT_UI_JWT"] = "dummy.jwt"
    app.config["CONSENT_UI_SRC"] = "https://consents.mastercard.com"

    state = "state-iframe"
    storage.save_pending_enrollments(
        [{"state": state, "created_at": 0, "return_url": "http://localhost/"}],
        base_dir=tmp_path,
    )

    resp = client.get(f"/enroll/ui/frame?state={state}")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "ConsentUI.js" in html


def test_enroll_ui_callback_success(app, client, tmp_path: Path):
    app.config["DATA_DIR"] = tmp_path

    state = "state-123"
    storage.save_pending_enrollments(
        [{"state": state, "created_at": 0, "return_url": "http://localhost/"}],
        base_dir=tmp_path,
    )

    payload = {
        "state": state,
        "message": {"type": "Close", "data": {"status": "success", "cardReference": "card-1"}},
    }
    resp = client.post("/enroll/ui/callback", json=payload)
    assert resp.status_code == 200

    enrollments = storage.load_enrollments(base_dir=tmp_path)
    assert enrollments[0]["card_reference"] == "card-1"

    pending = storage.load_pending_enrollments(base_dir=tmp_path)
    assert pending == []


def test_enroll_ui_callback_unknown_state(client):
    payload = {
        "state": "missing",
        "message": {"type": "Close", "data": {"status": "success"}},
    }
    resp = client.post("/enroll/ui/callback", json=payload)
    assert resp.status_code == 404


def test_enroll_ui_frame_missing_state(client):
    resp = client.get("/enroll/ui/frame")
    assert resp.status_code == 400


def test_debug_consent_ui_jwt_disabled(client, monkeypatch):
    monkeypatch.delenv("MC_DEBUG_CONSENT_UI", raising=False)
    resp = client.get("/debug/consent-ui-jwt")
    assert resp.status_code == 404


def test_debug_consent_ui_jwt_enabled(client, monkeypatch):
    monkeypatch.setenv("MC_DEBUG_CONSENT_UI", "1")
    now = int(datetime.now(timezone.utc).timestamp())
    token = jwt.encode(
        {
            "iat": now,
            "nbf": now,
            "exp": now + 300,
            "jti": "test",
            "appdata": {"callbackURL": "http://localhost"},
        },
        "secret",
        algorithm="HS256",
        headers={"typ": "JWT", "kid": "test-kid"},
    )
    client.application.config["CONSENT_UI_JWT"] = token

    resp = client.get("/debug/consent-ui-jwt")
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["header"]["kid"] == "test-kid"
    assert payload["token"] == token
