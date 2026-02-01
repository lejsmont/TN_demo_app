"""Payload encryption helpers for Mastercard APIs."""

from __future__ import annotations

import os
from typing import Any, Dict, Tuple

from client_encryption.api_encryption import ApiEncryption
from client_encryption.field_level_encryption_config import FieldLevelEncryptionConfig


def encryption_enabled() -> bool:
    return bool(os.getenv("MC_ENCRYPTION_CERT_PATH"))


def build_encryption_config(cert_path: str) -> FieldLevelEncryptionConfig:
    config = {
        "paths": {
            "$": {
                "toEncrypt": {"$": "$"},
                "toDecrypt": {},
            }
        },
        "encryptedValueFieldName": "encryptedData",
        "encryptedKeyFieldName": "encryptedKey",
        "ivFieldName": "iv",
        "oaepPaddingDigestAlgorithm": "SHA256",
        "dataEncoding": "BASE64",
        "encryptionCertificate": cert_path,
        "encryptionKeyFingerprintFieldName": "publicKeyFingerprint",
        "oaepPaddingDigestAlgorithmFieldName": "oaepHashingAlgorithm",
    }
    return FieldLevelEncryptionConfig(config)


def encrypt_payload_if_configured(
    payload: Dict[str, Any],
    headers: Dict[str, str] | None = None,
) -> Tuple[Dict[str, Any], Dict[str, str]]:
    headers = headers or {}
    cert_path = os.getenv("MC_ENCRYPTION_CERT_PATH")
    if not cert_path:
        return payload, headers

    conf = build_encryption_config(cert_path)
    encrypted_payload = ApiEncryption.encrypt_field_level_payload(headers, conf, payload)
    return encrypted_payload, headers
