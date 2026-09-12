from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

MCP_ROOT = Path(__file__).parents[1] / "mcp_server"
sys.path.insert(0, str(MCP_ROOT))

from research_search import QUERY_INSTRUCTION, ResearchSearch, build_filters  # noqa: E402


def response(columns: list[str], rows: list[list[object]]) -> SimpleNamespace:
    return SimpleNamespace(
        manifest=SimpleNamespace(columns=[SimpleNamespace(name=name) for name in columns]),
        result=SimpleNamespace(data_array=rows),
    )


def test_filter_contract_normalizes_values_and_validates_dates() -> None:
    assert build_filters(
        ["msft", " AAPL ", "AAPL"], ["ARTICLE", "filing"], "2025-01-01", "2026-01-01"
    ) == {
        "tickers": ["AAPL", "MSFT"],
        "source_type": ["article", "filing"],
        "source_date >=": "2025-01-01",
        "source_date <=": "2026-01-01",
    }
    with pytest.raises(ValueError, match="Unsupported source type"):
        build_filters(source_types=["note"])
    with pytest.raises(ValueError, match="on or before"):
        build_filters(start_date="2026-01-02", end_date="2026-01-01")


def test_hybrid_search_reranks_filters_and_deduplicates_parents() -> None:
    workspace = Mock()
    columns = ["chunk_id", "parent_id", "chunk_to_retrieve", "parent_text", "source_url"]
    workspace.vector_search_indexes.query_index.return_value = response(
        columns,
        [
            ["child-1", "parent-1", "passage one", "parent one", "https://example.test/1", "0.95"],
            ["child-2", "parent-1", "passage duplicate", "parent one", "https://example.test/1", "0.90"],
            ["child-3", "parent-2", "passage two", "parent two", "https://example.test/2", "0.85"],
        ],
    )
    result = ResearchSearch(workspace, index_name="catalog.schema.index").search(
        "material risks", top_k=2, tickers=["AAPL"], source_types=["filing"]
    )
    assert result["count"] == 2
    assert [match["parent_id"] for match in result["matches"]] == ["parent-1", "parent-2"]
    assert result["matches"][0]["score"] == 0.95
    assert result["matches"][0]["passage"] == "passage one"
    assert result["matches"][0]["context"] == "parent one"
    call = workspace.vector_search_indexes.query_index.call_args.kwargs
    assert call["query_type"] == "HYBRID"
    assert call["query_text"] == f"{QUERY_INSTRUCTION}material risks"
    assert call["num_results"] == 20
    assert "columns_to_rerank" not in call
    assert call["reranker"].model == "databricks_reranker"
    assert call["reranker"].parameters.columns_to_rerank == ["chunk_to_retrieve"]
    assert json.loads(call["filters_json"]) == {"source_type": ["filing"], "tickers": ["AAPL"]}


def test_empty_query_is_rejected_without_calling_search() -> None:
    workspace = Mock()
    with pytest.raises(ValueError, match="non-empty"):
        ResearchSearch(workspace).search("  ")
    workspace.vector_search_indexes.query_index.assert_not_called()
