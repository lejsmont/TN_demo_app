"""Hosted Consent UI JWT generation and config."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from oauth1 import authenticationutils


@dataclass
class ConsentUiConfig:
    src: str


def consent_ui_src() -> str:
    return os.getenv("MC_CONSENT_UI_SRC", "https://consents.mastercard.com")


def consent_ui_kid(consumer_key: str) -> str:
    if "!" in consumer_key:
        return consumer_key.split("!", 1)[0]
    return consumer_key


def generate_consent_ui_jwt(callback_origin: str) -> str:
    consumer_key = os.getenv("MC_CONSUMER_KEY")
    keystore_path = os.getenv("MC_KEYSTORE_PATH")
    keystore_password = os.getenv("MC_KEYSTORE_PASSWORD")

    if not consumer_key or not keystore_path or not keystore_password:
        raise ValueError("Missing MC_CONSUMER_KEY/MC_KEYSTORE_PATH/MC_KEYSTORE_PASSWORD for Consent UI JWT")

    signing_key = authenticationutils.load_signing_key(keystore_path, keystore_password)

    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=15)

    payload = {
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "jti": str(uuid4()),
        "appdata": {"callbackURL": callback_origin},
    }

    token = jwt.encode(
        payload,
        signing_key,
        algorithm="RS256",
        headers={"typ": "JWT", "alg": "RS256", "kid": consent_ui_kid(consumer_key)},
    )
    return token


def describe_consent_ui_jwt(token: str) -> dict:
    header = jwt.get_unverified_header(token)
    payload = jwt.decode(token, options={"verify_signature": False})
    return {"header": header, "payload": payload}
