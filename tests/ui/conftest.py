import threading

import pytest
from werkzeug.serving import make_server

from app import create_app


@pytest.fixture
def live_server(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "DATA_DIR": tmp_path,
            "CONSENT_UI_JWT": "dummy.jwt",
            "CONSENT_UI_SRC": "https://consents.mastercard.com",
        }
    )
    server = make_server("127.0.0.1", 0, app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", tmp_path
    finally:
        server.shutdown()
        thread.join(timeout=2)
