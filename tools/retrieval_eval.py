"""Evaluate managed research retrieval against labeled source identifiers."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from statistics import mean
from typing import Any

from databricks.sdk import WorkspaceClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mcp_server"))

from research_search import ResearchSearch  # noqa: E402

PROVENANCE_FIELDS = ("source_type", "source_id", "ticker", "title", "source_date", "source_url")


def _case_metrics(case: dict[str, Any], matches: list[dict[str, Any]]) -> dict[str, Any]:
    expected = set(case["expected_source_ids"])
    ranked = [str(match.get("source_id")) for match in matches]
    relevant_positions = [index for index, source_id in enumerate(ranked, start=1) if source_id in expected]
    retrieved_expected = expected.intersection(ranked)
    recall = len(retrieved_expected) / len(expected)
    reciprocal_rank = 1 / relevant_positions[0] if relevant_positions else 0.0
    dcg = sum(1 / math.log2(position + 1) for position in relevant_positions)
    ideal_count = min(len(expected), len(matches))
    ideal_dcg = sum(1 / math.log2(position + 1) for position in range(1, ideal_count + 1))
    ndcg = dcg / ideal_dcg if ideal_dcg else 0.0
    missing_provenance = [
        {"rank": rank, "fields": [field for field in PROVENANCE_FIELDS if match.get(field) in (None, "")]}
        for rank, match in enumerate(matches, start=1)
        if any(match.get(field) in (None, "") for field in PROVENANCE_FIELDS)
    ]

    filters = case.get("filters") or {}
    violations: list[dict[str, Any]] = []
    allowed_tickers = set(filters.get("tickers") or [])
    allowed_types = set(filters.get("source_types") or [])
    for rank, match in enumerate(matches, start=1):
        match_tickers = set(match.get("tickers") or [match.get("ticker")])
        source_date = str(match.get("source_date") or "")[:10]
        if allowed_tickers and not allowed_tickers.intersection(match_tickers):
            violations.append({"rank": rank, "filter": "tickers"})
        if allowed_types and match.get("source_type") not in allowed_types:
            violations.append({"rank": rank, "filter": "source_types"})
        if filters.get("start_date") and source_date < filters["start_date"]:
            violations.append({"rank": rank, "filter": "start_date"})
        if filters.get("end_date") and source_date > filters["end_date"]:
            violations.append({"rank": rank, "filter": "end_date"})

    return {
        "case_id": case["case_id"],
        "recall_at_k": recall,
        "reciprocal_rank": reciprocal_rank,
        "ndcg_at_k": ndcg,
        "result_count": len(matches),
        "missing_expected_source_ids": sorted(expected - retrieved_expected),
        "missing_provenance": missing_provenance,
        "filter_violations": violations,
    }


def evaluate_cases(cases: list[dict[str, Any]], search: ResearchSearch) -> dict[str, Any]:
    results = []
    for case in cases:
        filters = case.get("filters") or {}
        response = search.search(
            case["query"],
            top_k=case.get("top_k", 5),
            tickers=filters.get("tickers"),
            source_types=filters.get("source_types"),
            start_date=filters.get("start_date"),
            end_date=filters.get("end_date"),
        )
        results.append(_case_metrics(case, response["matches"]))
    provenance_failures = sum(len(result["missing_provenance"]) for result in results)
    filter_violations = sum(len(result["filter_violations"]) for result in results)
    summary = {
        "case_count": len(results),
        "recall_at_5": mean(result["recall_at_k"] for result in results) if results else 0.0,
        "mrr": mean(result["reciprocal_rank"] for result in results) if results else 0.0,
        "ndcg_at_5": mean(result["ndcg_at_k"] for result in results) if results else 0.0,
        "provenance_failures": provenance_failures,
        "filter_violations": filter_violations,
    }
    summary["passed"] = (
        summary["case_count"] >= 50
        and summary["recall_at_5"] >= 0.85
        and summary["mrr"] >= 0.70
        and provenance_failures == 0
        and filter_violations == 0
    )
    return {"summary": summary, "cases": results}


def load_cases(path: Path) -> list[dict[str, Any]]:
    cases = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(cases, list) or not cases:
        raise ValueError("Retrieval evaluation must contain at least one case.")
    for case in cases:
        if not case.get("case_id") or not case.get("query") or not case.get("expected_source_ids"):
            raise ValueError("Every case requires case_id, query, and expected_source_ids.")
    return cases


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True)
    parser.add_argument("--cases", type=Path, default=ROOT / "fixtures" / "retrieval" / "phase5_smoke.json")
    parser.add_argument("--index-name")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    search = ResearchSearch(WorkspaceClient(profile=args.profile), index_name=args.index_name)
    report = evaluate_cases(load_cases(args.cases), search)
    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(f"{rendered}\n", encoding="utf-8")
    print(rendered)
    return 0 if report["summary"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

