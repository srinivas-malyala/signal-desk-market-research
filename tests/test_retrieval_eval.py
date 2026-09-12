from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from tools.retrieval_eval import evaluate_cases, load_cases

ROOT = Path(__file__).resolve().parents[1]


def match(source_id: str, *, ticker: str = "AAPL", source_type: str = "filing") -> dict:
    return {
        "source_id": source_id,
        "source_type": source_type,
        "ticker": ticker,
        "tickers": [ticker],
        "title": "Example filing",
        "source_date": "2025-08-01",
        "source_url": "https://example.test/filing",
    }


def test_metrics_measure_rank_recall_provenance_and_filters() -> None:
    search = Mock()
    search.search.return_value = {"matches": [match("other"), match("expected")]}
    cases = [
        {
            "case_id": "case-1",
            "query": "question",
            "top_k": 5,
            "filters": {"tickers": ["AAPL"], "source_types": ["filing"]},
            "expected_source_ids": ["expected"],
        }
    ]
    report = evaluate_cases(cases, search)
    assert report["summary"]["recall_at_5"] == 1.0
    assert report["summary"]["mrr"] == 0.5
    assert report["summary"]["provenance_failures"] == 0
    assert report["summary"]["filter_violations"] == 0
    assert report["summary"]["passed"] is False  # Workspace acceptance requires at least 50 labels.


def test_missing_provenance_and_filter_violation_fail_quality_gate() -> None:
    search = Mock()
    invalid = match("expected", ticker="MSFT", source_type="article")
    invalid["source_url"] = None
    search.search.return_value = {"matches": [invalid]}
    report = evaluate_cases(
        [
            {
                "case_id": "case-1",
                "query": "question",
                "filters": {"tickers": ["AAPL"], "source_types": ["filing"]},
                "expected_source_ids": ["expected"],
            }
        ],
        search,
    )
    assert report["summary"]["provenance_failures"] == 1
    assert report["summary"]["filter_violations"] == 2


def test_case_loader_rejects_unlabeled_fixture(tmp_path: Path) -> None:
    path = tmp_path / "cases.json"
    path.write_text(json.dumps([{"case_id": "missing-label", "query": "question"}]))
    with pytest.raises(ValueError, match="expected_source_ids"):
        load_cases(path)


def test_workspace_fixture_meets_minimum_case_count() -> None:
    cases = load_cases(ROOT / "fixtures" / "retrieval" / "phase5_workspace.json")
    assert len(cases) >= 50


def test_duplicate_passages_from_one_source_do_not_inflate_ndcg() -> None:
    search = Mock()
    search.search.return_value = {
        "matches": [match("source-a"), match("source-a"), match("source-a")]
    }
    result = evaluate_cases(
        [
            {
                "case_id": "source-level-relevance",
                "query": "question",
                "expected_source_ids": ["source-a"],
            }
        ],
        search,
    )["cases"][0]
    assert result["ndcg_at_k"] == 1.0
