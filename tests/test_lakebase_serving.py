from __future__ import annotations

import sys
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock

import pytest

MCP_ROOT = Path(__file__).parents[1] / "mcp_server"
sys.path.insert(0, str(MCP_ROOT))

from lakebase_serving import (  # noqa: E402
    LakebaseResearchSearch,
    fetch_latest_market_bars,
    fetch_market_bars,
    market_backend,
    research_backend,
    serving_schema,
)


def _connection(rows: list[dict]):
    cursor = Mock()
    cursor.__enter__ = Mock(return_value=cursor)
    cursor.__exit__ = Mock(return_value=False)
    cursor.fetchall.return_value = rows
    connection = Mock()
    connection.cursor.return_value = cursor
    return connection, cursor


def test_backend_and_identifier_configuration_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    assert market_backend() == "databricks"
    assert research_backend() == "databricks"

    monkeypatch.setenv("SIGNAL_DESK_MARKET_BACKEND", "unknown")
    with pytest.raises(ValueError, match="MARKET_BACKEND"):
        market_backend()

    monkeypatch.setenv("SIGNAL_DESK_RESEARCH_BACKEND", "lakebase_pgvector")
    with pytest.raises(RuntimeError, match="reserved"):
        research_backend()

    monkeypatch.setenv("SIGNAL_DESK_SERVING_SCHEMA", "unsafe-name")
    with pytest.raises(ValueError, match="SERVING_SCHEMA"):
        serving_schema()


def test_market_serving_query_is_parameterized_bounded_and_normalized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SIGNAL_DESK_SERVING_SCHEMA", "bootcamp_students")
    connection, cursor = _connection(
        [
            {
                "date": date(2026, 9, 10),
                "open": Decimal("100.25"),
                "close": Decimal("110.50"),
                "volume": Decimal("2000"),
                "daily_return": Decimal("0.1"),
                "source_request_id": "request-id",
                "source_freshness_at": datetime(2026, 9, 11, tzinfo=UTC),
            }
        ]
    )

    rows = fetch_market_bars("AAPL", "2026-09-01", "2026-09-10", connection=connection)

    assert rows[0]["date"] == "2026-09-10"
    assert rows[0]["open"] == 100.25
    assert rows[0]["volume"] == 2000.0
    assert rows[0]["source_freshness_at"] == "2026-09-11T00:00:00+00:00"
    sql, params = cursor.execute.call_args.args
    assert "bootcamp_students.market_history_serving_srini" in sql
    assert "LIMIT 370" in sql
    assert "AAPL" not in sql
    assert params == ("AAPL", "2026-09-01", "2026-09-10")


def test_latest_market_bars_are_bounded_to_requested_watchlist_tickers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SIGNAL_DESK_SERVING_SCHEMA", "bootcamp_students")
    connection, cursor = _connection(
        [
            {
                "ticker": "MSFT",
                "close": Decimal("425.50"),
                "change_percent": Decimal("1.25"),
                "captured_at": "2026-09-30",
            }
        ]
    )

    rows = fetch_latest_market_bars([" msft ", "MSFT"], connection=connection)

    assert rows == [
        {
            "ticker": "MSFT",
            "close": 425.5,
            "change_percent": 1.25,
            "captured_at": "2026-09-30",
        }
    ]
    sql, params = cursor.execute.call_args.args
    assert "bootcamp_students.market_history_serving_srini" in sql
    assert "DISTINCT ON (ticker)" in sql
    assert "daily_return * 100 AS change_percent" in sql
    assert "MSFT" not in sql
    assert params == (["MSFT"], 1)


def test_latest_market_bars_skips_database_for_empty_ticker_list() -> None:
    connection, cursor = _connection([])

    assert fetch_latest_market_bars([], connection=connection) == []
    cursor.execute.assert_not_called()


def test_full_text_search_filters_deduplicates_and_labels_nonsemantic_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SIGNAL_DESK_SERVING_SCHEMA", "bootcamp_students")
    connection, cursor = _connection(
        [
            {
                "chunk_id": "child-1",
                "parent_id": "parent-1",
                "passage": "Material risk one.",
                "context": "Parent one.",
                "source_date": date(2026, 9, 1),
                "score": Decimal("0.95"),
            },
            {
                "chunk_id": "child-2",
                "parent_id": "parent-1",
                "passage": "Duplicate parent.",
                "context": "Parent one.",
                "source_date": date(2026, 9, 1),
                "score": Decimal("0.90"),
            },
            {
                "chunk_id": "child-3",
                "parent_id": "parent-2",
                "passage": "Material risk two.",
                "context": "Parent two.",
                "source_date": date(2026, 9, 2),
                "score": Decimal("0.85"),
            },
        ]
    )

    result = LakebaseResearchSearch(connection).search(
        "material risks",
        top_k=2,
        tickers=["aapl"],
        source_types=["filing"],
        start_date="2026-01-01",
        end_date="2026-12-31",
    )

    assert result["count"] == 2
    assert result["retrieval"]["backend"] == "lakebase_fts"
    assert result["retrieval"]["query_type"] == "POSTGRES_FULL_TEXT"
    assert [row["parent_id"] for row in result["matches"]] == ["parent-1", "parent-2"]
    assert result["matches"][0]["score"] == 0.95
    assert "not a semantic" in result["limitations"][0]
    sql, params = cursor.execute.call_args.args
    assert "bootcamp_students.research_documents_serving_srini" in sql
    assert "websearch_to_tsquery" in sql
    assert params == (
        "material risks",
        "material risks",
        ["AAPL"],
        ["AAPL"],
        ["filing"],
        "2026-01-01",
        "2026-12-31",
        20,
    )


def test_full_text_search_rejects_invalid_inputs() -> None:
    connection, _ = _connection([])
    search = LakebaseResearchSearch(connection)
    with pytest.raises(ValueError, match="non-empty"):
        search.search(" ")
    with pytest.raises(ValueError, match="Unsupported"):
        search.search("risk", source_types=["note"])
    with pytest.raises(ValueError, match="on or before"):
        search.search("risk", start_date="2026-02-01", end_date="2026-01-01")
