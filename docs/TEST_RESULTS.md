# Test Results

## F01 — App scaffold, config, and health check
Date: 2026-01-31
- Command: `.venv/bin/pytest -q`
- Result: PASS (3 passed)

## F02 — Filesystem JSON storage module
Date: 2026-01-31
- Command: `.venv/bin/pytest -q`
- Result: PASS (9 passed)

## F03 — Mastercard API client wrapper (OAuth1 signer + errors)
Date: 2026-01-31
- Command: `.venv/bin/pytest -q`
- Result: PASS (14 passed)
- Command: `.venv/bin/pytest --cov=app --cov-report=term-missing`
- Result: PASS (total coverage 88%)

## F04 — Consent Management API enrollment flow
Date: 2026-01-31
- Command: `.venv/bin/pytest -q`
- Result: PASS (18 passed)
- Command: `.venv/bin/pytest --cov=app --cov-report=term-missing`
- Result: PASS (total coverage 88%)

## F12A — Consent Management sandbox E2E verification (pulled forward)
Date: 2026-01-31
- Command: `.venv/bin/pytest -q`
- Result: PASS (18 passed, 1 skipped)
- Command: `.venv/bin/pytest --cov=app --cov-report=term-missing`
- Result: PASS (total coverage 88%, 1 skipped)
- Command: `RUN_E2E=1 .venv/bin/pytest -q tests/e2e`
- Result: PASS (1 passed)

## F05 — Hosted Consent UI redirect + callback flow
Date: 2026-01-31
- Command: `pytest -q`
- Result: PASS (25 passed, 1 skipped)
- Command: `pytest --cov=app --cov-report=term-missing`
- Result: PASS (total coverage 86%, 1 skipped)

## F06 — Web UI pages (three tabs + dashboard)
Date: 2026-01-31
- Command: `pytest -q`
- Result: PASS (25 passed, 1 skipped)
- Command: `pytest --cov=app --cov-report=term-missing`
- Result: PASS (total coverage 86%, 1 skipped)

## F07 — Transaction posting flow
Date: 2026-01-31
- Command: `pytest -q`
- Result: PASS (31 passed, 1 skipped)
- Command: `pytest --cov=app --cov-report=term-missing`
- Result: PASS (total coverage 85%, 1 skipped)

## F08 — Undelivered notifications poll + reconcile
Date: 2026-01-31
- Command: `pytest -q`
- Result: PASS (44 passed, 1 skipped)
- Command: `pytest --cov=app --cov-report=term-missing`
- Result: PASS (total coverage 80%, 1 skipped)

## F11 — UI E2E tests (Playwright, required)
Date: 2026-02-01
- Command: `.venv/bin/pytest -q`
- Result: PASS (47 passed, 1 skipped)
- Command: `.venv/bin/pytest --cov=app --cov-report=term-missing`
- Result: PASS (total coverage 81%, 1 skipped)

## UI — Notification filtering, dedupe, and pagination
Date: 2026-02-01
- Command: `.venv/bin/pytest -q`
- Result: PASS (49 passed, 2 skipped)
- Command: `.venv/bin/pytest --cov=app --cov-report=term-missing`
- Result: PASS (total coverage 80%, 2 skipped)

## F12B — Transaction Notifications sandbox E2E verification
Date: 2026-02-01
- Command: `.venv/bin/pytest -q`
- Result: PASS (49 passed, 2 skipped)
- Command: `.venv/bin/pytest --cov=app --cov-report=term-missing`
- Result: PASS (total coverage 80%, 2 skipped)
- Command: `RUN_E2E=1 .venv/bin/pytest -q tests/e2e`
- Result: PASS (2 passed)

## F13 — Documentation pack (README, dev, deploy)
Date: 2026-02-01
- Command: `.venv/bin/pytest -q`
- Result: PASS (49 passed, 2 skipped)
- Command: `.venv/bin/pytest --cov=app --cov-report=term-missing`
- Result: PASS (total coverage 80%, 2 skipped)
- Command: `RUN_E2E=1 .venv/bin/pytest -q tests/e2e`
- Result: PASS (2 passed)

## F14 — 3DS flow integration (late feature)
Date: 2026-02-01
- Command: `.venv/bin/pytest -q`
- Result: PASS (56 passed, 2 skipped)
- Command: `.venv/bin/pytest --cov=app --cov-report=term-missing`
- Result: PASS (total coverage 81%, 2 skipped)
- Command: `RUN_E2E=1 .venv/bin/pytest -q tests/e2e`
- Result: PASS (2 passed)

## UI — 3DS overlay + start-auth payload normalization
Date: 2026-02-01
- Command: `.venv/bin/pytest -q tests/integration/test_3ds_flow.py`
- Result: PASS (5 passed)

## UI — 3DS fingerprintStatus lowercase normalization
Date: 2026-02-01
- Command: `.venv/bin/pytest -q tests/integration/test_3ds_flow.py`
- Result: PASS (5 passed)

## UI — 3DS accept/user-agent header alignment
Date: 2026-02-01
- Command: `.venv/bin/pytest -q tests/integration/test_3ds_flow.py`
- Result: PASS (5 passed)

## Debug — MC error body surfaced when reason/description missing
Date: 2026-02-01
- Command: `.venv/bin/pytest -q tests/unit/test_mc_client.py`
- Result: PASS (5 passed)

## Fix — Encrypt 3DS start/verify authentication payloads
Date: 2026-02-01
- Command: `.venv/bin/pytest -q tests/integration/test_3ds_flow.py`
- Result: PASS (5 passed)

## Fix — 3DS merchantName length normalization
Date: 2026-02-01
- Command: `.venv/bin/pytest -q tests/integration/test_3ds_flow.py`
- Result: PASS (5 passed)

## UI — 3DS challenge iframe sizing + full-screen window size
Date: 2026-02-01
- Command: `.venv/bin/pytest -q tests/integration/test_3ds_flow.py`
- Result: PASS (5 passed)

## Fix — Enrollment de-duplication on re-enroll
Date: 2026-02-01
- Command: `.venv/bin/pytest -q tests/integration/test_enroll_api.py tests/integration/test_3ds_flow.py`
- Result: PASS (8 passed)

## Fix — Enrollment de-duplication on load/save
Date: 2026-02-01
- Command: `.venv/bin/pytest -q tests/unit/test_storage.py`
- Result: PASS (7 passed)

## UI — Button hover/focus highlights + remove health link
Date: 2026-02-01
- Command: Not run (UI-only change)
- Result: N/A
