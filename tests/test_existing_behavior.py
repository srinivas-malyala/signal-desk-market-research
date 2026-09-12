from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
MCP_ROOT = ROOT / "mcp_server"
if str(MCP_ROOT) not in sys.path:
    sys.path.insert(0, str(MCP_ROOT))

import research_broker as broker  # noqa: E402
from massive_client import MassiveClient  # noqa: E402


def test_existing_ticker_normalization_is_characterized() -> None:
    assert broker._symbol(" brk.b ") == "BRK.B"
    with pytest.raises(ValueError):
        broker._symbol("not a ticker")


def test_existing_http_error_mapping_is_characterized() -> None:
    response = Mock(status_code=429)
    error = broker.requests.HTTPError(response=response)
    result = broker._error(error)
    assert result == {
        "status": "error",
        "error_code": "massive_http_429",
        "message": "The Massive API rate limit was reached. Try again shortly.",
    }


def test_existing_massive_pagination_is_characterized(monkeypatch: pytest.MonkeyPatch) -> None:
    client = MassiveClient(api_key="fixture-key")
    responses = [
        {"results": [{"id": 1}, {"id": 2}], "next_url": "https://example.test/page/2"},
        {"results": [{"id": 3}]},
    ]
    get = Mock(side_effect=responses)
    monkeypatch.setattr(client, "get", get)
    assert list(client.paginated_get("/page/1", {"ticker": "AAPL"})) == [
        {"id": 1},
        {"id": 2},
        {"id": 3},
    ]
    assert get.call_args_list[1].args == ("https://example.test/page/2", None)


def test_existing_watchlist_add_semantics_are_characterized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_write(sql, _params=None, returning=False):
        if "RETURNING id" in sql:
            return {"id": 7 if "users" in sql else 11}
        return 1

    monkeypatch.setattr(broker.lakebase, "write", fake_write)
    monkeypatch.setattr(broker.lakebase, "query", lambda *_args: [])
    result = broker.update_watchlist("person@example.com", " aapl ", "add")
    assert result["status"] == "success"
    assert result["ticker"] == "AAPL"
    assert result["action"] == "add"
    assert result["tickers"] == []


def test_existing_note_and_report_response_shapes_are_characterized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_write(sql, _params=None, returning=False):
        if "users_srini" in sql:
            return {"id": 7}
        if "research_notes_srini" in sql:
            return {"id": 21, "created_at": "2026-09-10T12:00:00Z"}
        if "analysis_reports_srini" in sql:
            return {"id": 22, "created_at": "2026-09-10T12:01:00Z"}
        return 1

    monkeypatch.setattr(broker.lakebase, "write", fake_write)
    note = broker.save_research_note("person@example.com", "aapl", "Thesis", "Evidence")
    report = broker.save_analysis_report(
        "person@example.com",
        "Comparison",
        "Relative value",
        ["aapl", "msft"],
        "Evidence-backed report",
    )
    assert set(note) == {"status", "note_id", "ticker", "created_at"}
    assert note["note_id"] == 21
    assert report["report_id"] == 22
    assert report["tickers"] == ["AAPL", "MSFT"]


def test_all_nine_mcp_tool_functions_remain_declared() -> None:
    source = (MCP_ROOT / "stock_research_mcp_server.py").read_text()
    expected = {
        "get_stock_performance",
        "get_company_research",
        "compare_stocks",
        "get_watchlist",
        "update_watchlist",
        "save_research_note",
        "save_analysis_report",
        "semantic_research",
        "get_notable_updates",
    }
    declared = {
        line.removeprefix("def ").split("(", 1)[0]
        for line in source.splitlines()
        if line.startswith("def ")
    }
    assert expected <= declared


def test_embedding_job_compatibility_entry_point_now_requests_managed_sync() -> None:
    spec = importlib.util.spec_from_file_location("embedding_job", ROOT / "jobs" / "ingest_research_embeddings.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    workspace = Mock()
    workspace.vector_search_indexes.get_index.return_value.status.ready = True
    result = module.run("catalog.schema.index", workspace)
    assert result == {"status": "sync_requested", "index": "catalog.schema.index", "prior_ready": True}
    workspace.vector_search_indexes.sync_index.assert_called_once_with(index_name="catalog.schema.index")
