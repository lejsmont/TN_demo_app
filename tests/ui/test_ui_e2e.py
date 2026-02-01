import re

import pytest
from playwright.sync_api import expect

from app import storage


@pytest.mark.ui
def test_dashboard_shows_notification_details(page, live_server):
    base_url, data_dir = live_server
    storage.save_enrollments(
        [
            {
                "id": "consent-1",
                "consent_id": "consent-1",
                "card_reference": "card-ref-1",
                "card_alias": "Test Card - 0297",
                "pan_last4": "0297",
                "status": "APPROVED",
                "created_at": "2026-01-31T00:00:00Z",
            }
        ],
        base_dir=data_dir,
    )
    storage.save_notifications(
        [
            {
                "id": "note-1",
                "card_reference": "card-ref-1",
                "merchant": "Demo Merchant",
                "amount": "12.34",
                "currency": "USD",
                "event_time": "2026-01-31T00:01:00Z",
                "status": "UNDELIVERED",
                "received_at": "2026-01-31T00:01:05Z",
            }
        ],
        base_dir=data_dir,
    )

    page.goto(f"{base_url}/?tab=dashboard", wait_until="domcontentloaded")
    notifications_table = page.locator("#tab-dashboard .panel-card.span-2 table")
    expect(notifications_table.get_by_text("Demo Merchant")).to_be_visible()
    expect(notifications_table.get_by_text("12.34 USD")).to_be_visible()
    expect(notifications_table.get_by_text("Test Card - 0297")).to_be_visible()


@pytest.mark.ui
def test_hosted_consent_ui_wrapper(page, live_server):
    base_url, _ = live_server
    page.goto(f"{base_url}/enroll/ui/start", wait_until="domcontentloaded")
    expect(page.get_by_text("Hosted Consent UI")).to_be_visible()
    frame = page.locator("iframe")
    expect(frame).to_have_attribute("src", re.compile(r"/enroll/ui/frame"))
