import os
import tempfile

_tmp = tempfile.mkdtemp()
# Default: SQLite sementara. Untuk tes di PostgreSQL: TEST_DATABASE_URL=postgresql+psycopg2://... pytest
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{_tmp}/test.db"
os.environ["UPLOAD_DIR"] = f"{_tmp}/uploads"
os.environ["DEBUG"] = "true"  # tanpa SMTP: email hanya ditangkap oleh fixture outbox

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    from tests.demo_data import load_demo_data

    with TestClient(app) as c:  # startup membuat tabel (kosong)
        load_demo_data()  # data dummy hanya untuk tes ini, pada database sementara
        yield c


@pytest.fixture(scope="session")
def tokens(client):
    out = {}
    for name in ("admin", "hrd", "hrd2", "finance", "finance2", "employee", "employee2"):
        r = client.post("/auth/login", data={"username": f"{name}@kantor.test", "password": "Password123!"})
        assert r.status_code == 200, r.text
        out[name] = {"Authorization": f"Bearer {r.json()['access_token']}"}
    return out


@pytest.fixture(autouse=True)
def outbox(monkeypatch):
    """Menangkap email berisi password sementara / token reset (tidak ada email sungguhan terkirim)."""
    from app.services import email_utils

    box: list[dict] = []

    def capture(to, subject, body):
        box.append({"to": list(to), "subject": subject, "body": body})

    monkeypatch.setattr(email_utils, "send_now", capture)
    monkeypatch.setattr(email_utils, "send_secret_async", capture)
    return box
