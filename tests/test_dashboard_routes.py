from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

pytest.importorskip("flask")

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_ROOT = ROOT / "dashboard"


@pytest.fixture
def app_module(monkeypatch: pytest.MonkeyPatch):
    fake_db = Mock()
    fake_db.write.return_value = {"id": 1}
    fake_db.query.return_value = []
    monkeypatch.setitem(sys.modules, "lakebase", fake_db)
    spec = importlib.util.spec_from_file_location("dashboard_app", DASHBOARD_ROOT / "app.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.app.config.update(TESTING=True)
    return module


def test_existing_health_route(app_module) -> None:
    response = app_module.app.test_client().get("/healthz")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_existing_watchlist_validation(app_module) -> None:
    response = app_module.app.test_client().post("/api/watchlist", json={"ticker": "not valid"})
    assert response.status_code == 400
    assert response.get_json()["status"] == "error"
