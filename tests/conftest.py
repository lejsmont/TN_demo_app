import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from app import create_app  # noqa: E402


@pytest.fixture
def app():
    app = create_app({"TESTING": True, "APP_NAME": "Test App"})
    yield app


@pytest.fixture
def client(app):
    return app.test_client()
