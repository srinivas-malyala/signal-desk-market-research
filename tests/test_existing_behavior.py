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
    update = Mock(
        return_value={
            "status": "success",
            "ticker": "AAPL",
            "action": "add",
            "tickers": [],
            "idempotent_replay": False,
        }
    )
    refresh_profile = Mock()
    monkeypatch.setattr(broker.actions, "update_watchlist", update)
    monkeypatch.setattr(broker, "_refresh_company_profile", refresh_profile)
    result = broker.update_watchlist(
        "person@example.com", " aapl ", "add", confirmed=True, idempotency_key="request-123"
    )
    assert result["status"] == "success"
    assert result["ticker"] == "AAPL"
    assert result["action"] == "add"
    assert result["tickers"] == []
    update.assert_called_once_with(
        "person@example.com", "AAPL", "add", "Primary", confirmed=True, idempotency_key="request-123"
    )
    refresh_profile.assert_called_once_with("AAPL")


def test_watchlist_profile_enrichment_failure_does_not_undo_confirmed_add(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    update = Mock(
        return_value={
            "status": "success",
            "ticker": "MSFT",
            "action": "add",
            "changed": True,
            "idempotent_replay": False,
        }
    )
    monkeypatch.setattr(broker.actions, "update_watchlist", update)
    monkeypatch.setattr(
        broker,
        "_refresh_company_profile",
        Mock(side_effect=RuntimeError("profile provider unavailable")),
    )

    result = broker.update_watchlist(
        "person@example.com", "MSFT", "add", confirmed=True, idempotency_key="request-456"
    )

    assert result["status"] == "success"
    assert result["changed"] is True


def test_watchlist_remove_and_idempotent_replay_skip_profile_enrichment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    refresh_profile = Mock()
    monkeypatch.setattr(broker, "_refresh_company_profile", refresh_profile)
    monkeypatch.setattr(
        broker.actions,
        "update_watchlist",
        Mock(return_value={"status": "success", "action": "remove", "idempotent_replay": False}),
    )
    broker.update_watchlist(
        "person@example.com", "MSFT", "remove", confirmed=True, idempotency_key="request-remove"
    )
    monkeypatch.setattr(
        broker.actions,
        "update_watchlist",
        Mock(return_value={"status": "success", "action": "add", "idempotent_replay": True}),
    )
    broker.update_watchlist(
        "person@example.com", "MSFT", "add", confirmed=True, idempotency_key="request-replay"
    )

    refresh_profile.assert_not_called()


def test_watchlist_uses_lakebase_serving_prices_when_market_backend_is_active(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    legacy_rows = [
        {
            "ticker": "MSFT",
            "added_at": "time",
            "name": None,
            "description": None,
            "market_cap": None,
            "close": None,
            "change_percent": None,
            "captured_at": None,
        }
    ]
    monkeypatch.setattr(broker.lakebase, "query", Mock(return_value=legacy_rows))
    monkeypatch.setenv("SIGNAL_DESK_MARKET_BACKEND", "lakebase")
    latest = Mock(
        return_value=[
            {
                "ticker": "MSFT",
                "close": 425.5,
                "change_percent": 1.25,
                "captured_at": "2026-09-30",
            }
        ]
    )
    monkeypatch.setattr("lakebase_serving.fetch_latest_market_bars", latest)

    result = broker.get_watchlist("person@example.com")

    assert result["status"] == "success"
    assert result["tickers"][0]["ticker"] == "MSFT"
    assert result["tickers"][0]["close"] == 425.5
    assert result["tickers"][0]["change_percent"] == 1.25
    assert result["tickers"][0]["captured_at"] == "2026-09-30"
    latest.assert_called_once_with(["MSFT"])


def test_watchlist_keeps_legacy_snapshot_when_market_serving_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    legacy_rows = [
        {
            "ticker": "AAPL",
            "close": 338.4,
            "change_percent": -0.78,
            "captured_at": "2026-09-28T04:00:00+00:00",
        }
    ]
    monkeypatch.setattr(broker.lakebase, "query", Mock(return_value=legacy_rows))
    monkeypatch.setenv("SIGNAL_DESK_MARKET_BACKEND", "lakebase")
    monkeypatch.setattr(
        "lakebase_serving.fetch_latest_market_bars",
        Mock(side_effect=RuntimeError("serving table temporarily unavailable")),
    )

    result = broker.get_watchlist("person@example.com")

    assert result == {"status": "success", "watchlist": "Primary", "tickers": legacy_rows}


def test_watchlist_does_not_replace_a_newer_legacy_snapshot_with_older_serving_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    legacy_rows = [
        {
            "ticker": "AAPL",
            "close": 338.4,
            "change_percent": -0.78,
            "captured_at": "2026-09-28T04:00:00+00:00",
        }
    ]
    monkeypatch.setattr(broker.lakebase, "query", Mock(return_value=legacy_rows))
    monkeypatch.setenv("SIGNAL_DESK_MARKET_BACKEND", "lakebase")
    monkeypatch.setattr(
        "lakebase_serving.fetch_latest_market_bars",
        Mock(
            return_value=[
                {
                    "ticker": "AAPL",
                    "close": 230.0,
                    "change_percent": 0.5,
                    "captured_at": "2026-09-09",
                }
            ]
        ),
    )

    result = broker.get_watchlist("person@example.com")

    assert result["tickers"][0]["close"] == 338.4
    assert result["tickers"][0]["change_percent"] == -0.78
    assert result["tickers"][0]["captured_at"] == "2026-09-28T04:00:00+00:00"


def test_existing_note_and_report_response_shapes_are_characterized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        broker.actions,
        "save_research_note",
        Mock(return_value={"status": "success", "note_id": 21, "ticker": "AAPL", "created_at": "time"}),
    )
    monkeypatch.setattr(
        broker.actions,
        "save_analysis_report",
        Mock(return_value={"status": "success", "report_id": 22, "tickers": ["AAPL", "MSFT"], "created_at": "time"}),
    )
    note = broker.save_research_note(
        "person@example.com", "aapl", "Thesis", "Evidence", confirmed=True, idempotency_key="request-note-1"
    )
    report = broker.save_analysis_report(
        "person@example.com",
        "Comparison",
        "Relative value",
        ["aapl", "msft"],
        "Evidence-backed report",
        confirmed=True,
        idempotency_key="request-report-1",
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
    for function_name in ("get_watchlist", "update_watchlist", "save_research_note", "save_analysis_report", "get_notable_updates"):
        declaration = next(line for line in source.splitlines() if line.startswith(f"def {function_name}(") )
        assert "user_email" not in declaration
    assert '@mcp.custom_route("/health", methods=["GET"])' in source
    assert 'response.headers["x-request-id"]' in source


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
