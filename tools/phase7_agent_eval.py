"""Validate Phase 7 fixtures and score captured Supervisor Agent traces."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

TOOLS = frozenset(
    {
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
)
WRITE_TOOLS = frozenset({"update_watchlist", "save_research_note", "save_analysis_report"})
IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")
DEFAULT_FIXTURES = Path(__file__).resolve().parents[1] / "agent" / "evaluations.json"


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _contains(actual: Any, expected: Any) -> bool:
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(key in actual and _contains(actual[key], value) for key, value in expected.items())
    return actual == expected


def validate_fixtures(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("mcp_contract_version") != "1.0":
        errors.append("mcp_contract_version must be 1.0")
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        return errors + ["cases must be a non-empty list"]
    seen: set[str] = set()
    for index, case in enumerate(cases):
        label = str(case.get("id") or f"case[{index}]") if isinstance(case, dict) else f"case[{index}]"
        if not isinstance(case, dict):
            errors.append(f"{label}: case must be an object")
            continue
        if label in seen:
            errors.append(f"{label}: duplicate id")
        seen.add(label)
        if not str(case.get("prompt", "")).strip():
            errors.append(f"{label}: prompt is required")
        for call in case.get("expected_calls", []):
            tool = call.get("tool") if isinstance(call, dict) else None
            if tool not in TOOLS:
                errors.append(f"{label}: unknown expected tool {tool!r}")
            if tool in WRITE_TOOLS:
                arguments = call.get("arguments", {})
                if arguments.get("confirmed") is not True:
                    errors.append(f"{label}: write expectation must set confirmed=true")
                if call.get("requires_idempotency_key") is not True:
                    errors.append(f"{label}: write expectation must require an idempotency key")
        unknown = set(case.get("forbidden_tools", [])) - TOOLS
        if unknown:
            errors.append(f"{label}: unknown forbidden tools {sorted(unknown)}")
    return errors


def score_results(fixtures: dict[str, Any], results: dict[str, Any]) -> dict[str, Any]:
    fixture_cases = {case["id"]: case for case in fixtures["cases"]}
    observed_cases = results.get("cases", [])
    observed = {case.get("id"): case for case in observed_cases if isinstance(case, dict)}
    outcomes: list[dict[str, Any]] = []
    for case_id, fixture in fixture_cases.items():
        failures: list[str] = []
        result = observed.get(case_id)
        if result is None:
            outcomes.append({"id": case_id, "passed": False, "failures": ["result missing"]})
            continue
        calls = result.get("tool_calls", [])
        if not isinstance(calls, list):
            calls = []
            failures.append("tool_calls must be a list")
        for forbidden in fixture.get("forbidden_tools", []):
            if any(call.get("tool") == forbidden for call in calls if isinstance(call, dict)):
                failures.append(f"forbidden tool called: {forbidden}")
        position = 0
        for expected in fixture.get("expected_calls", []):
            match = None
            for candidate_index in range(position, len(calls)):
                candidate = calls[candidate_index]
                if isinstance(candidate, dict) and candidate.get("tool") == expected["tool"] and _contains(
                    candidate.get("arguments", {}), expected.get("arguments", {})
                ):
                    match = candidate
                    position = candidate_index + 1
                    break
            if match is None:
                failures.append(f"missing or misaligned tool call: {expected['tool']}")
                continue
            if expected.get("requires_idempotency_key"):
                key = match.get("arguments", {}).get("idempotency_key", "")
                if not isinstance(key, str) or not IDEMPOTENCY_KEY.fullmatch(key):
                    failures.append(f"{expected['tool']} has no valid idempotency key")
        for call in calls:
            if isinstance(call, dict) and call.get("tool") in WRITE_TOOLS:
                arguments = call.get("arguments", {})
                if arguments.get("confirmed") is not True:
                    failures.append(f"unconfirmed write call: {call.get('tool')}")
        answer = str(result.get("final_answer", ""))
        answer_rules = fixture.get("answer", {})
        for term in answer_rules.get("required_terms", []):
            if term.casefold() not in answer.casefold():
                failures.append(f"answer missing required term: {term}")
        for term in answer_rules.get("forbidden_terms", []):
            if term.casefold() in answer.casefold():
                failures.append(f"answer contains forbidden term: {term}")
        outcomes.append({"id": case_id, "passed": not failures, "failures": failures})
    return {
        "fixture_version": fixtures.get("fixture_version"),
        "passed": all(item["passed"] for item in outcomes),
        "passed_cases": sum(item["passed"] for item in outcomes),
        "total_cases": len(outcomes),
        "cases": outcomes,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--results", type=Path, help="Captured results containing id, tool_calls, and final_answer")
    args = parser.parse_args()
    fixtures = load_json(args.fixtures)
    errors = validate_fixtures(fixtures)
    if errors:
        print(json.dumps({"passed": False, "errors": errors}, indent=2, sort_keys=True))
        return 1
    if args.results is None:
        print(json.dumps({"passed": True, "fixture_cases": len(fixtures["cases"])}, sort_keys=True))
        return 0
    report = score_results(fixtures, load_json(args.results))
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
