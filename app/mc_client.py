"""Mastercard API client wrapper with OAuth1 signing, retries, and error mapping."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import requests
from oauth1 import authenticationutils, signer as oauth_signer
from requests import PreparedRequest, Response, Session
from tenacity import retry, retry_if_exception_type, retry_if_result, stop_after_attempt, wait_exponential_jitter

logger = logging.getLogger(__name__)

SENSITIVE_HEADERS = {"authorization"}
SENSITIVE_FIELDS = {"pan", "full_pan", "card_number", "cvc", "cvv"}


@dataclass
class MastercardApiError(Exception):
    status_code: int
    reason_code: str | None
    description: str | None
    correlation_id: str | None

    def __str__(self) -> str:
        return (
            f"MastercardApiError(status={self.status_code}, reason={self.reason_code}, "
            f"correlation_id={self.correlation_id})"
        )


@dataclass
class ClientConfig:
    base_url: str
    timeout_seconds: float = 30.0
    max_retries: int = 3
    backoff_seconds: float = 0.5
    user_agent: str = "tn-demo-app/1.0"


def validate_env_and_keystore() -> None:
    required = ["MC_CONSUMER_KEY", "MC_KEYSTORE_PASSWORD", "MC_KEYSTORE_PATH"]
    missing = [key for key in required if not os.getenv(key)]
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
    keystore_path = Path(os.getenv("MC_KEYSTORE_PATH", ""))
    if not keystore_path.exists():
        raise FileNotFoundError(f"Keystore not found: {keystore_path}")


class MastercardApiClient:
    def __init__(
        self,
        config: ClientConfig,
        consumer_key: str,
        keystore_path: str,
        keystore_password: str,
        session: Session | None = None,
        signer: oauth_signer.OAuthSigner | None = None,
    ) -> None:
        self.config = config
        self.consumer_key = consumer_key
        self.keystore_path = keystore_path
        self.keystore_password = keystore_password
        self.session = session or requests.Session()

        if signer is None:
            self._validate_params()
            signing_key = authenticationutils.load_signing_key(self.keystore_path, self.keystore_password)
            signer = oauth_signer.OAuthSigner(self.consumer_key, signing_key)
        self.signer = signer

    @classmethod
    def from_env(cls, base_url: str) -> "MastercardApiClient":
        return cls(
            config=ClientConfig(base_url=base_url),
            consumer_key=os.getenv("MC_CONSUMER_KEY", ""),
            keystore_path=os.getenv("MC_KEYSTORE_PATH", ""),
            keystore_password=os.getenv("MC_KEYSTORE_PASSWORD", ""),
        )

    def _validate_params(self) -> None:
        missing = []
        if not self.consumer_key:
            missing.append("consumer_key")
        if not self.keystore_path:
            missing.append("keystore_path")
        if not self.keystore_password:
            missing.append("keystore_password")
        if missing:
            raise ValueError(f"Missing required parameters: {', '.join(missing)}")
        if not Path(self.keystore_path).exists():
            raise FileNotFoundError(f"Keystore not found: {self.keystore_path}")

    def _prepare_request(
        self,
        method: str,
        url: str,
        headers: Dict[str, str] | None,
        params: Dict[str, Any] | None,
        json_body: Dict[str, Any] | None,
    ) -> PreparedRequest:
        req = requests.Request(method=method, url=url, headers=headers, params=params, json=json_body)
        prepared = self.session.prepare_request(req)
        signed_url = prepared.url or url
        self.signer.sign_request(signed_url, prepared)
        prepared.headers.setdefault("User-Agent", self.config.user_agent)
        return prepared

    def _send_with_retry(self, prepared: PreparedRequest) -> Response:
        @retry(
            stop=stop_after_attempt(self.config.max_retries),
            wait=wait_exponential_jitter(initial=self.config.backoff_seconds, max=5),
            retry=(
                retry_if_exception_type(requests.RequestException)
                | retry_if_result(lambda resp: resp is not None and resp.status_code >= 500)
            ),
            reraise=True,
        )
        def _send() -> Response:
            return self.session.send(prepared, timeout=self.config.timeout_seconds)

        return _send()

    def request(
        self,
        method: str,
        path: str,
        *,
        headers: Dict[str, str] | None = None,
        params: Dict[str, Any] | None = None,
        json_body: Dict[str, Any] | None = None,
        allow_retry: bool | None = None,
    ) -> Response:
        url = f"{self.config.base_url.rstrip('/')}/{path.lstrip('/')}"
        prepared = self._prepare_request(method, url, headers, params, json_body)
        self._log_request(prepared)

        if allow_retry is None:
            allow_retry = method.upper() in {"GET", "HEAD", "OPTIONS"}

        response = self._send_with_retry(prepared) if allow_retry else self.session.send(
            prepared, timeout=self.config.timeout_seconds
        )

        if response.status_code >= 400:
            raise self._build_error(response)

        return response

    def _log_request(self, prepared: PreparedRequest) -> None:
        headers = _redact_headers(dict(prepared.headers))
        logger.debug("MC request %s %s headers=%s", prepared.method, prepared.url, headers)

    def _build_error(self, response: Response) -> MastercardApiError:
        reason_code = None
        description = None
        correlation_id = _correlation_id(response)
        raw_text = None
        try:
            payload = response.json()
            reason_code = payload.get("ReasonCode") or payload.get("reasonCode")
            description = payload.get("Description") or payload.get("description")
            if description is None and payload is not None:
                description = json.dumps(payload)
        except (ValueError, json.JSONDecodeError):
            payload = None
        if description is None:
            try:
                raw_text = response.text
            except Exception:
                raw_text = None
            if raw_text:
                description = raw_text[:2000]
        logger.warning("MC error status=%s correlation_id=%s payload=%s", response.status_code, correlation_id, _redact_payload(payload))
        return MastercardApiError(
            status_code=response.status_code,
            reason_code=reason_code,
            description=description,
            correlation_id=correlation_id,
        )


def _correlation_id(response: Response) -> str | None:
    return response.headers.get("Correlation-Id") or response.headers.get("X-Correlation-ID")


def _redact_headers(headers: Dict[str, str]) -> Dict[str, str]:
    redacted = {}
    for key, value in headers.items():
        if key.lower() in SENSITIVE_HEADERS:
            redacted[key] = "[redacted]"
        else:
            redacted[key] = value
    return redacted


def _redact_payload(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {k: ("[redacted]" if k in SENSITIVE_FIELDS else _redact_payload(v)) for k, v in payload.items()}
    if isinstance(payload, list):
        return [_redact_payload(item) for item in payload]
    return payload
