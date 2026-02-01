import os

import pytest

from app.config import AppConfig


def test_validate_required_raises_on_missing(monkeypatch):
    monkeypatch.delenv("MC_CONSUMER_KEY", raising=False)

    with pytest.raises(ValueError) as excinfo:
        AppConfig.validate_required(["MC_CONSUMER_KEY"])

    assert "MC_CONSUMER_KEY" in str(excinfo.value)


def test_from_env_reads_values(monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.setenv("FLASK_DEBUG", "0")
    monkeypatch.setenv("APP_NAME", "Custom App")

    cfg = AppConfig.from_env()

    assert cfg.env == "production"
    assert cfg.debug is False
    assert cfg.app_name == "Custom App"
