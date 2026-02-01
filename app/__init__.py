"""Flask application factory."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from flask import Flask, jsonify, render_template, request, url_for

from .config import AppConfig, load_env
from .consent_service import (
    build_enrollment_record,
    enroll_card_via_api,
    parse_auth_details,
    parse_card_details,
    start_authentication,
    verify_authentication,
)
from .consent_ui import consent_ui_src, describe_consent_ui_jwt, generate_consent_ui_jwt
from .mc_client import MastercardApiError, MastercardApiClient, validate_env_and_keystore
from .notification_service import (
    build_notification_record,
    ensure_notification_fingerprint,
    enrich_notification_record,
    notification_fingerprint,
    poll_undelivered_notifications,
)
from .storage import (
    load_enrollments,
    load_notifications,
    load_pending_enrollments,
    load_pending_authentications,
    load_transactions,
    save_enrollments,
    save_notifications,
    save_pending_enrollments,
    save_pending_authentications,
    save_transactions,
)
from .transaction_service import (
    build_transaction_record,
    generate_transaction_identifiers,
    parse_transaction_input,
    post_transaction,
)


def create_app(test_config: dict | None = None) -> Flask:
    load_env()
    app = Flask(__name__)

    config = AppConfig.from_env()
    app.config.update(config.as_flask_dict())

    if test_config:
        app.config.update(test_config)

    test_cards = [
        {
            "label": "Success + 3DS challenge (PAN 2303…0297)",
            "pan": "2303779951000297",
            "expiry_month": 12,
            "expiry_year": 2027,
            "cvc": "123",
            "cardholder_name": "John",
        },
        {
            "label": "Success + 3DS frictionless (PAN 5204…9999)",
            "pan": "5204730541009999",
            "expiry_month": 12,
            "expiry_year": 2027,
            "cvc": "123",
            "cardholder_name": "frictionless",
        },
        {
            "label": "Success + 3DS not supported (PAN 5555…4444)",
            "pan": "5555555555554444",
            "expiry_month": 12,
            "expiry_year": 2027,
            "cvc": "123",
            "cardholder_name": "John",
        },
        {
            "label": "Pre-auth stolen card (PAN 5555…4242)",
            "pan": "5555424242424242",
            "expiry_month": 12,
            "expiry_year": 2027,
            "cvc": "123",
            "cardholder_name": "John",
        },
        {
            "label": "3DS auth failure (PAN 2303…0248)",
            "pan": "2303779951000248",
            "expiry_month": 12,
            "expiry_year": 2027,
            "cvc": "123",
            "cardholder_name": "John",
        },
    ]

    def _find_pending_auth(pending: list, *, state: str | None = None, card_reference: str | None = None):
        for item in pending:
            if state and item.get("state") == state:
                return item
            if card_reference and item.get("card_reference") == card_reference:
                return item
        return None

    def _pop_pending_auth(pending: list, state: str | None = None) -> dict | None:
        for idx, item in enumerate(pending):
            if state and item.get("state") == state:
                return pending.pop(idx)
        return None

    def _normalize_fingerprint_status(value: str | None) -> str:
        if not value:
            return "unavailable"
        normalized = value.strip().lower()
        mapping = {
            "complete": "complete",
            "completed": "complete",
            "success": "complete",
            "timeout": "timeout",
            "unavailable": "unavailable",
            "not_available": "unavailable",
            "notavailable": "unavailable",
        }
        return mapping.get(normalized, normalized)

    def _parse_int(value: str | None) -> int | None:
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _parse_bool(value: str | None) -> bool | None:
        if value in (None, ""):
            return None
        text = str(value).strip().lower()
        if text in {"true", "1", "yes", "y"}:
            return True
        if text in {"false", "0", "no", "n"}:
            return False
        return None

    def _normalize_color_depth(value: str | None) -> int | None:
        depth = _parse_int(value)
        if depth is None:
            return None
        allowed = [1, 4, 8, 15, 16, 24, 32, 48]
        if depth in allowed:
            return depth
        return min(allowed, key=lambda candidate: abs(candidate - depth))

    def _is_loopback_ip(value: str | None) -> bool:
        if not value:
            return False
        return value.startswith("127.") or value == "::1"

    def _normalize_merchant_name(value: str | None) -> str | None:
        if not value:
            return None
        text = str(value).strip()
        if not text:
            return None
        return text[:40]

    def _find_enrollment_index(enrollments: list, record: dict) -> int | None:
        record_ref = record.get("card_reference")
        if record_ref:
            for idx, existing in enumerate(enrollments):
                if existing.get("card_reference") == record_ref:
                    return idx
        record_last4 = record.get("pan_last4")
        record_alias = record.get("card_alias")
        if record_last4:
            for idx, existing in enumerate(enrollments):
                if existing.get("pan_last4") != record_last4:
                    continue
                if record_alias and existing.get("card_alias") and existing.get("card_alias") != record_alias:
                    continue
                return idx
        record_consent = record.get("consent_id") or record.get("id")
        if record_consent:
            for idx, existing in enumerate(enrollments):
                if existing.get("consent_id") == record_consent or existing.get("id") == record_consent:
                    return idx
        return None

    def _upsert_enrollment(enrollments: list, record: dict) -> None:
        idx = _find_enrollment_index(enrollments, record)
        if idx is None:
            enrollments.append(record)
        else:
            enrollments[idx] = {**enrollments[idx], **record}

    def _finalize_enrollment_from_pending(
        pending: dict,
        *,
        consent_status: str | None,
        auth_status: str | None,
    ) -> None:
        data_dir = app.config.get("DATA_DIR")
        enrollments = load_enrollments(base_dir=data_dir)
        record = {
            "id": pending.get("consent_id"),
            "consent_id": pending.get("consent_id"),
            "card_reference": pending.get("card_reference"),
            "card_alias": pending.get("card_alias") or pending.get("card_reference"),
            "pan_last4": pending.get("pan_last4"),
            "status": consent_status or "APPROVED",
            "auth_status": auth_status,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        _upsert_enrollment(enrollments, record)
        save_enrollments(enrollments, base_dir=data_dir)

    def _normalize_amount(value: object) -> str | None:
        if value in (None, ""):
            return None
        try:
            return str(Decimal(str(value)).normalize())
        except (InvalidOperation, ValueError):
            return str(value).strip()

    def _normalize_text(value: object) -> str | None:
        if value in (None, ""):
            return None
        return str(value).strip().upper()

    def _parse_timestamp(value: object) -> float:
        if value in (None, ""):
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return 0.0
            if text.endswith("Z"):
                text = text[:-1] + "+00:00"
            if len(text) >= 5 and text[-5] in "+-" and text[-2:].isdigit() and text[-4:-2].isdigit():
                if text[-3] != ":":
                    text = text[:-2] + ":" + text[-2:]
            try:
                return datetime.fromisoformat(text).timestamp()
            except ValueError:
                for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z"):
                    try:
                        return datetime.strptime(text, fmt).timestamp()
                    except ValueError:
                        continue
        return 0.0

    def _notification_match_key(item: dict) -> tuple[str, str, str, str] | None:
        card_ref = item.get("card_reference") or item.get("consent_id")
        amount = _normalize_amount(item.get("amount"))
        currency = _normalize_text(item.get("currency"))
        merchant = _normalize_text(item.get("merchant"))
        if card_ref and amount and currency and merchant:
            return (str(card_ref).strip(), amount, currency, merchant)
        return None

    def _filter_notifications(notifications: list, transactions: list) -> tuple[list, str, bool]:
        if not transactions:
            return notifications, "all notifications", False

        reference_numbers = {
            str(txn.get("reference_number")).strip()
            for txn in transactions
            if txn.get("reference_number")
        }
        stan_numbers = {
            str(txn.get("system_trace_audit_number")).strip()
            for txn in transactions
            if txn.get("system_trace_audit_number")
        }
        fallback_keys = {
            key
            for txn in transactions
            for key in (_notification_match_key(txn),)
            if key is not None
        }

        if not reference_numbers and not stan_numbers and not fallback_keys:
            return notifications, "all notifications", False

        filtered: list = []
        for note in notifications:
            ref = note.get("reference_number")
            if ref and str(ref).strip() in reference_numbers:
                filtered.append(note)
                continue
            stan = note.get("system_trace_audit_number")
            if stan and str(stan).strip() in stan_numbers:
                filtered.append(note)
                continue
            key = _notification_match_key(note)
            if key and key in fallback_keys:
                filtered.append(note)

        return filtered, "filtered to UI-posted transactions", True

    def _dedupe_notifications(notifications: list) -> tuple[list, bool]:
        deduped: list = []
        seen: set[str] = set()
        changed = False
        for note in notifications:
            key = note.get("fingerprint") or notification_fingerprint(note) or note.get("id")
            if not key:
                deduped.append(note)
                continue
            key_str = str(key)
            if key_str in seen:
                changed = True
                continue
            seen.add(key_str)
            deduped.append(note)
        return deduped, changed

    def render_index(active_tab: str, post_result: dict | None = None) -> str:
        data_dir = app.config.get("DATA_DIR")
        enrollments = load_enrollments(base_dir=data_dir)
        transactions = load_transactions(base_dir=data_dir)
        notifications = load_notifications(base_dir=data_dir)
        updated = False
        for note in notifications:
            if enrich_notification_record(note):
                updated = True
            if not note.get("fingerprint"):
                if ensure_notification_fingerprint(note):
                    updated = True
        notifications, deduped = _dedupe_notifications(notifications)
        if deduped:
            updated = True
        if updated:
            save_notifications(notifications, base_dir=data_dir)

        transactions_sorted = sorted(
            transactions,
            key=lambda item: _parse_timestamp(item.get("posted_at") or item.get("created_at")),
            reverse=True,
        )

        notifications_total = len(notifications)
        notifications_filtered, filter_label, filter_active = _filter_notifications(
            notifications, transactions_sorted
        )
        notifications_sorted = sorted(
            notifications_filtered,
            key=lambda item: _parse_timestamp(
                item.get("event_time") or item.get("received_at") or item.get("created_at")
            ),
            reverse=True,
        )
        notifications_filtered_total = len(notifications_sorted)

        page_size = 8
        page_raw = request.args.get("notif_page", "1")
        try:
            page = int(page_raw)
        except ValueError:
            page = 1
        if page < 1:
            page = 1
        total_pages = max(1, (notifications_filtered_total + page_size - 1) // page_size)
        if page > total_pages:
            page = total_pages
        start_index = (page - 1) * page_size
        end_index = min(start_index + page_size, notifications_filtered_total)
        notifications_page = notifications_sorted[start_index:end_index]

        card_labels = {}
        for enrollment in enrollments:
            ref = enrollment.get("card_reference") or enrollment.get("consent_id")
            if not ref:
                continue
            card_labels[ref] = enrollment.get("card_alias") or ref
        return render_template(
            "index.html",
            enrollments=enrollments,
            transactions=transactions_sorted,
            notifications=notifications_page,
            notifications_total=notifications_total,
            notifications_filtered_total=notifications_filtered_total,
            notifications_filter_label=filter_label,
            notifications_filter_active=filter_active,
            notifications_page=page,
            notifications_page_total=total_pages,
            notifications_page_start=0 if notifications_filtered_total == 0 else start_index + 1,
            notifications_page_end=end_index,
            active_tab=active_tab,
            test_cards=test_cards,
            post_result=post_result,
            card_labels=card_labels,
        )

    @app.get("/")
    def index():
        active_tab = request.args.get("tab", "enroll")
        if active_tab not in {"enroll", "post", "dashboard"}:
            active_tab = "enroll"
        return render_index(active_tab)

    @app.get("/dashboard")
    def dashboard():
        return render_index("dashboard")

    @app.get("/healthz")
    def healthz():
        return jsonify({"status": "ok", "app": app.config.get("APP_NAME")}), 200

    @app.post("/enroll/api")
    def enroll_api():
        payload = request.get_json(silent=True) or {}
        consent_name = payload.get("consent_name") or "notification"
        try:
            card = parse_card_details(payload)
        except ValueError as exc:
            return jsonify({"success": False, "message": str(exc)}), 400

        client = app.config.get("CONSENTS_CLIENT")
        if client is None:
            validate_env_and_keystore()
            base_url = app.config.get("CONSENTS_BASE_URL") or os.getenv(
                "MC_BASE_URL_CONSENTS", "https://sandbox.api.mastercard.com/openapis/authentication"
            )
            client = MastercardApiClient.from_env(base_url)

        try:
            result = enroll_card_via_api(client, card, consent_name=consent_name)
        except MastercardApiError as exc:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": f"Consent API error ({exc.reason_code or exc.status_code})",
                        "correlation_id": exc.correlation_id,
                    }
                ),
                502,
            )

        if not result.success:
            return jsonify({"success": False, "message": result.message}), 502

        auth_details = parse_auth_details(result.raw or {})
        auth_type = auth_details.auth_type
        auth_status = auth_details.auth_status

        if auth_type == "THREEDS" and auth_status in {
            "AUTH_READY_TO_START",
            "AUTH_IN_PROGRESS",
            "AUTH_FAILED_CAN_RETRY",
        }:
            data_dir = app.config.get("DATA_DIR")
            pending_auths = load_pending_authentications(base_dir=data_dir)
            state = os.urandom(16).hex()
            pending_auths.append(
                {
                    "state": state,
                    "card_reference": result.card_reference,
                    "consent_id": result.consent_id,
                    "card_alias": build_enrollment_record(result, card).get("card_alias"),
                    "pan_last4": card.pan[-4:],
                    "consent_status": result.consent_status,
                    "auth_type": auth_type,
                    "auth_status": auth_status,
                    "auth_params": auth_details.auth_params or {},
                    "created_at": int(time.time()),
                }
            )
            save_pending_authentications(pending_auths, base_dir=data_dir)
            return (
                jsonify(
                    {
                        "success": True,
                        "auth_required": True,
                        "message": "3DS authentication required. Redirecting to fingerprinting.",
                        "redirect_url": url_for("enroll_3ds_fingerprint", state=state),
                    }
                ),
                200,
            )

        data_dir = app.config.get("DATA_DIR")
        enrollments = load_enrollments(base_dir=data_dir)
        record = build_enrollment_record(result, card)
        _upsert_enrollment(enrollments, record)
        save_enrollments(enrollments, base_dir=data_dir)

        return (
            jsonify(
                {
                    "success": True,
                    "message": result.message,
                    "consent_id": result.consent_id,
                    "card_reference": result.card_reference,
                }
            ),
            200,
        )

    @app.get("/enroll/3ds/fingerprint")
    def enroll_3ds_fingerprint():
        state = request.args.get("state")
        if not state:
            return "Missing state", 400

        data_dir = app.config.get("DATA_DIR")
        pending_auths = load_pending_authentications(base_dir=data_dir)
        pending = _find_pending_auth(pending_auths, state=state)
        if not pending:
            return "Unknown state", 404

        params = pending.get("auth_params") or {}

        def _param(*keys):
            for key in keys:
                value = params.get(key)
                if value not in (None, ""):
                    return value
            return ""

        return render_template(
            "3ds_fingerprint.html",
            three_ds_method_url=_param("threeDsMethodUrl", "threeDSMethodUrl", "threeDSMethodURL"),
            three_ds_method_notification_url=_param(
                "threeDSMethodNotificationURL", "threeDsMethodNotificationURL", "threeDsMethodNotificationUrl"
            ),
            three_ds_method_data=_param("threeDSMethodData", "threeDsMethodData"),
            three_ds_server_trans_id=_param("threeDSServerTransID", "threeDsServerTransId"),
            state=state,
            start_auth_url=url_for("enroll_3ds_start_authentication"),
        )

    @app.post("/enroll/3ds/start-authentication")
    def enroll_3ds_start_authentication():
        state = request.form.get("state") or request.args.get("state")
        if not state:
            return "Missing state", 400

        data_dir = app.config.get("DATA_DIR")
        pending_auths = load_pending_authentications(base_dir=data_dir)
        pending = _find_pending_auth(pending_auths, state=state)
        if not pending:
            return "Unknown state", 404

        auth_type = pending.get("auth_type") or "THREEDS"
        fingerprint_status = _normalize_fingerprint_status(request.form.get("fingerprintStatus"))
        accept_header = request.headers.get("Accept") or request.form.get("browserAcceptHeader")
        if not accept_header:
            accept_header = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        accept_language = request.headers.get("Accept-Language", "")
        language = accept_language.split(",")[0] if accept_language else None
        if not language:
            language = request.form.get("browserLanguage")
        user_agent = request.headers.get("User-Agent") or request.form.get("browserUserAgent")
        merchant_name = _normalize_merchant_name(os.getenv("MC_MERCHANT_NAME") or app.config.get("APP_NAME"))
        auth_params = {
            "fingerprintStatus": fingerprint_status,
            "merchantName": merchant_name,
            "browserAcceptHeader": accept_header,
            "browserColorDepth": _normalize_color_depth(request.form.get("browserColorDepth")),
            "browserJavaEnabled": _parse_bool(request.form.get("browserJavaEnabled")),
            "browserLanguage": language,
            "browserScreenHeight": _parse_int(request.form.get("browserScreenHeight")),
            "browserScreenWidth": _parse_int(request.form.get("browserScreenWidth")),
            "browserTZ": _parse_int(request.form.get("browserTZ")),
            "browserUserAgent": user_agent,
            "challengeWindowSize": request.form.get("challengeWindowSize", "05"),
        }
        browser_ip = request.headers.get("X-Forwarded-For") or request.remote_addr
        if browser_ip:
            browser_ip = browser_ip.split(",")[0].strip()
            if _is_loopback_ip(browser_ip):
                env_ip = os.getenv("MC_BROWSER_IP")
                if env_ip:
                    auth_params["browserIP"] = env_ip
            else:
                auth_params["browserIP"] = browser_ip
        auth_params = {key: value for key, value in auth_params.items() if value not in (None, "")}

        client = app.config.get("CONSENTS_CLIENT")
        if client is None:
            validate_env_and_keystore()
            base_url = app.config.get("CONSENTS_BASE_URL") or os.getenv(
                "MC_BASE_URL_CONSENTS", "https://sandbox.api.mastercard.com/openapis/authentication"
            )
            client = MastercardApiClient.from_env(base_url)

        try:
            response = start_authentication(client, pending["card_reference"], auth_type, auth_params)
        except MastercardApiError as exc:
            detail_payload = {
                "reason_code": exc.reason_code,
                "description": exc.description,
                "correlation_id": exc.correlation_id,
                "auth_params": auth_params,
            }
            return (
                render_template(
                    "3ds_result.html",
                    success=False,
                    message=f"Start authentication failed ({exc.reason_code or exc.status_code})",
                    details=json.dumps(detail_payload, indent=2, sort_keys=True),
                ),
                502,
            )

        auth = parse_auth_details(response)
        if auth.auth_status == "AUTHENTICATED":
            _finalize_enrollment_from_pending(
                pending,
                consent_status="APPROVED",
                auth_status=auth.auth_status,
            )
            _pop_pending_auth(pending_auths, state=state)
            save_pending_authentications(pending_auths, base_dir=data_dir)
            return render_template(
                "3ds_result.html",
                success=True,
                message="Authentication complete. Consent approved.",
                details=None,
            )

        if auth.auth_status in {"AUTH_IN_PROGRESS", "AUTH_READY_TO_START"}:
            params = auth.auth_params or {}
            acs_url = params.get("acsUrl")
            encoded_creq = params.get("encodedCReq") or params.get("encodedCreq")
            if not acs_url or not encoded_creq:
                return render_template(
                    "3ds_result.html",
                    success=False,
                    message="Challenge parameters missing from start-authentication response.",
                    details=str(params) if params else None,
                )
            return render_template(
                "3ds_challenge.html",
                acs_url=acs_url,
                encoded_creq=encoded_creq,
                state=state,
            )

        return render_template(
            "3ds_result.html",
            success=False,
            message=f"Authentication failed (status={auth.auth_status})",
            details=str(auth.auth_params) if auth.auth_params else None,
        )

    @app.route("/enroll/3ds/verify", methods=["GET", "POST"])
    def enroll_3ds_verify():
        state = request.args.get("state") or request.form.get("state")
        if not state:
            return "Missing state", 400

        data_dir = app.config.get("DATA_DIR")
        pending_auths = load_pending_authentications(base_dir=data_dir)
        pending = _find_pending_auth(pending_auths, state=state)
        if not pending:
            return "Unknown state", 404

        auth_type = pending.get("auth_type") or "THREEDS"

        client = app.config.get("CONSENTS_CLIENT")
        if client is None:
            validate_env_and_keystore()
            base_url = app.config.get("CONSENTS_BASE_URL") or os.getenv(
                "MC_BASE_URL_CONSENTS", "https://sandbox.api.mastercard.com/openapis/authentication"
            )
            client = MastercardApiClient.from_env(base_url)

        try:
            response = verify_authentication(client, pending["card_reference"], auth_type, {})
        except MastercardApiError as exc:
            return (
                render_template(
                    "3ds_result.html",
                    success=False,
                    message=f"Verify authentication failed ({exc.reason_code or exc.status_code})",
                    details=exc.description or exc.reason_code,
                ),
                502,
            )

        auth = parse_auth_details(response)
        consents = response.get("consents") or []
        consent_status = consents[0].get("status") if consents else "APPROVED"

        if auth.auth_status == "AUTHENTICATED":
            _finalize_enrollment_from_pending(
                pending,
                consent_status=consent_status,
                auth_status=auth.auth_status,
            )
            _pop_pending_auth(pending_auths, state=state)
            save_pending_authentications(pending_auths, base_dir=data_dir)
            return render_template(
                "3ds_result.html",
                success=True,
                message="Authentication verified. Consent approved.",
                details=None,
            )

        return render_template(
            "3ds_result.html",
            success=False,
            message=f"Authentication failed (status={auth.auth_status})",
            details=str(auth.auth_params) if auth.auth_params else None,
        )

    @app.post("/transactions")
    def post_transactions():
        payload = request.get_json(silent=True)
        if payload is None:
            payload = request.form.to_dict()

        try:
            txn_input = parse_transaction_input(payload)
        except ValueError as exc:
            error = {"success": False, "message": str(exc)}
            if request.is_json:
                return jsonify(error), 400
            return render_index("post", post_result=error), 400

        data_dir = app.config.get("DATA_DIR")
        enrollments = load_enrollments(base_dir=data_dir)
        match = next((item for item in enrollments if item.get("card_reference") == txn_input.card_reference), None)
        consent_id = match.get("consent_id") if match else None
        card_alias = match.get("card_alias") if match else None

        client = app.config.get("TXN_CLIENT")
        if client is None:
            validate_env_and_keystore()
            base_url = app.config.get("TXN_BASE_URL") or os.getenv(
                "MC_BASE_URL_TXN_NOTIF", "https://sandbox.api.mastercard.com/openapis"
            )
            client = MastercardApiClient.from_env(base_url)

        try:
            identifiers = generate_transaction_identifiers()
            result = post_transaction(
                client,
                txn_input,
                reference_number=identifiers.reference_number,
                system_trace_audit_number=identifiers.system_trace_audit_number,
            )
            record = build_transaction_record(
                txn_input,
                status="POSTED",
                correlation_id=result.correlation_id,
                consent_id=consent_id,
                card_alias=card_alias,
                reference_number=identifiers.reference_number,
                system_trace_audit_number=identifiers.system_trace_audit_number,
            )
            message = result.message
        except MastercardApiError as exc:
            record = build_transaction_record(
                txn_input,
                status="FAILED",
                correlation_id=exc.correlation_id,
                consent_id=consent_id,
                card_alias=card_alias,
                error=exc.description or exc.reason_code,
                reference_number=None,
                system_trace_audit_number=None,
            )
            message = f"Transaction API error ({exc.reason_code or exc.status_code})"

        transactions = load_transactions(base_dir=data_dir)
        transactions.append(record)
        save_transactions(transactions, base_dir=data_dir)

        response_payload = {
            "success": record["status"] == "POSTED",
            "message": message,
            "correlation_id": record.get("correlation_id"),
        }

        if request.is_json:
            status_code = 200 if response_payload["success"] else 502
            return jsonify(response_payload), status_code

        status_code = 200 if response_payload["success"] else 502
        return render_index("post", post_result=response_payload), status_code

    @app.get("/notifications/undelivered")
    def get_undelivered_notifications():
        data_dir = app.config.get("DATA_DIR")
        card_reference = request.args.get("card_reference") or request.args.get("cardReference")
        after = request.args.get("after")
        attempts_raw = request.args.get("attempts", "3")

        try:
            attempts = max(1, min(int(attempts_raw), 5))
        except ValueError:
            attempts = 3

        after_value = None
        if after:
            try:
                after_value = int(after)
            except ValueError:
                after_value = None

        client = app.config.get("TXN_CLIENT")
        if client is None:
            validate_env_and_keystore()
            base_url = app.config.get("TXN_BASE_URL") or os.getenv(
                "MC_BASE_URL_TXN_NOTIF", "https://sandbox.api.mastercard.com/openapis"
            )
            client = MastercardApiClient.from_env(base_url)

        try:
            result = poll_undelivered_notifications(
                client,
                card_reference=card_reference,
                after=after_value,
                max_attempts=attempts,
            )
        except MastercardApiError as exc:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": f"Transaction Notifications API error ({exc.reason_code or exc.status_code})",
                        "correlation_id": exc.correlation_id,
                    }
                ),
                502,
            )

        new_records = [build_notification_record(item) for item in result.notifications]
        existing = load_notifications(base_dir=data_dir)
        existing_map = {item.get("id"): item for item in existing if item.get("id")}
        existing_fingerprint_map = {}
        for item in existing:
            if not item.get("fingerprint"):
                ensure_notification_fingerprint(item)
            fingerprint = item.get("fingerprint")
            if fingerprint:
                existing_fingerprint_map[fingerprint] = item

        for record in new_records:
            if not record.get("fingerprint"):
                ensure_notification_fingerprint(record)
            record_id = record.get("id")
            fingerprint = record.get("fingerprint")

            current = None
            if record_id and record_id in existing_map:
                current = existing_map[record_id]
            elif fingerprint and fingerprint in existing_fingerprint_map:
                current = existing_fingerprint_map[fingerprint]

            if current:
                for field in (
                    "merchant",
                    "amount",
                    "currency",
                    "event_time",
                    "card_reference",
                    "encrypted_payload",
                    "reference_number",
                    "system_trace_audit_number",
                    "trans_uid",
                    "notification_sequence_id",
                    "message_type",
                    "fingerprint",
                ):
                    if not current.get(field) and record.get(field) is not None:
                        current[field] = record[field]
                if record.get("payload") and not current.get("payload"):
                    current["payload"] = record["payload"]
                continue

            existing.append(record)
        save_notifications(existing, base_dir=data_dir)

        response_payload = {
            "success": result.found if card_reference else True,
            "message": result.message,
            "attempts": result.attempts,
            "found": result.found,
            "stored": len(new_records),
        }
        status_code = 200 if response_payload["success"] or not card_reference else 404
        return jsonify(response_payload), status_code

    @app.get("/enroll/ui/start")
    def enroll_ui_start():
        data_dir = app.config.get("DATA_DIR")
        state = os.urandom(16).hex()
        pending = load_pending_enrollments(base_dir=data_dir)
        pending.append({"state": state, "created_at": int(time.time()), "return_url": request.url_root})
        save_pending_enrollments(pending, base_dir=data_dir)
        frame_url = url_for("enroll_ui_frame", state=state)

        return render_template("consent_ui_wrapper.html", frame_url=frame_url)

    @app.get("/enroll/ui/frame")
    def enroll_ui_frame():
        state = request.args.get("state")
        if not state:
            return "Missing state", 400

        data_dir = app.config.get("DATA_DIR")
        pending = load_pending_enrollments(base_dir=data_dir)
        match = next((item for item in pending if item.get("state") == state), None)
        if not match:
            return "Unknown state", 404

        callback_origin = request.url_root.rstrip("/")
        callback_url = callback_origin + "/enroll/ui/callback"
        consent_jwt = app.config.get("CONSENT_UI_JWT") or generate_consent_ui_jwt(callback_origin)
        consent_src = app.config.get("CONSENT_UI_SRC") or consent_ui_src()

        return render_template(
            "consent_ui.html",
            consent_ui_src=consent_src,
            consent_jwt=consent_jwt,
            callback_url=callback_url,
            state=state,
        )

    @app.post("/enroll/ui/callback")
    def enroll_ui_callback():
        payload = request.get_json(silent=True) or {}
        state = payload.get("state")
        message = payload.get("message") or {}

        if not state:
            return jsonify({"success": False, "message": "Missing state"}), 400

        data_dir = app.config.get("DATA_DIR")
        pending = load_pending_enrollments(base_dir=data_dir)
        match = next((item for item in pending if item.get("state") == state), None)
        if not match:
            return jsonify({"success": False, "message": "Unknown state"}), 404

        msg_type = message.get("type")
        msg_data = message.get("data") or {}

        if msg_type == "Close" and msg_data.get("status") == "success":
            card_reference = msg_data.get("cardReference")
            enrollments = load_enrollments(base_dir=data_dir)
            record = {
                "id": card_reference,
                "consent_id": None,
                "card_reference": card_reference,
                "card_alias": f"Hosted UI - {card_reference}",
                "pan_last4": None,
                "status": "APPROVED",
                "auth_status": None,
                "created_at": int(time.time()),
            }
            _upsert_enrollment(enrollments, record)
            save_enrollments(enrollments, base_dir=data_dir)

            pending = [item for item in pending if item.get("state") != state]
            save_pending_enrollments(pending, base_dir=data_dir)
            return jsonify({"success": True, "message": "Enrollment completed", "card_reference": card_reference})

        if msg_type in {"Error", "Cancel", "Close"}:
            pending = [item for item in pending if item.get("state") != state]
            save_pending_enrollments(pending, base_dir=data_dir)
            return jsonify({"success": False, "message": msg_data.get("errorMessage") or msg_type})

        return jsonify({"success": True, "message": "Message received"})

    @app.get("/debug/consent-ui-jwt")
    def debug_consent_ui_jwt():
        if os.getenv("MC_DEBUG_CONSENT_UI") != "1":
            return jsonify({"error": "Consent UI debug disabled"}), 404

        callback_origin = request.url_root.rstrip("/")
        token = app.config.get("CONSENT_UI_JWT")
        if not token:
            try:
                token = generate_consent_ui_jwt(callback_origin)
            except ValueError as exc:
                return jsonify({"error": str(exc)}), 400

        details = describe_consent_ui_jwt(token)
        details.update(
            {
                "token": token,
                "callback_origin": callback_origin,
                "consent_ui_src": app.config.get("CONSENT_UI_SRC") or consent_ui_src(),
            }
        )
        return jsonify(details)

    return app
