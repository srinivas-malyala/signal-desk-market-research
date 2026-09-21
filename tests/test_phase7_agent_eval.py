from __future__ import annotations

import json
from pathlib import Path

from tools.phase7_agent_eval import DEFAULT_FIXTURES, load_json, score_results, validate_fixtures


def test_phase7_fixtures_match_final_mcp_contract() -> None:
    fixtures = load_json(DEFAULT_FIXTURES)
    assert validate_fixtures(fixtures) == []
    assert len(fixtures["cases"]) == 10


def test_evaluator_accepts_aligned_confirmed_write(tmp_path: Path) -> None:
    fixtures = load_json(DEFAULT_FIXTURES)
    fixtures["cases"] = [case for case in fixtures["cases"] if case["id"] == "watchlist_confirmed_write"]
    results = {
        "cases": [
            {
                "id": "watchlist_confirmed_write",
                "tool_calls": [
                    {
                        "tool": "update_watchlist",
                        "arguments": {
                            "ticker": "NVDA",
                            "action": "add",
                            "watchlist_name": "Primary",
                            "confirmed": True,
                            "idempotency_key": "watchlist-nvda-0001",
                        },
                    },
                    {"tool": "get_watchlist", "arguments": {"watchlist_name": "Primary"}},
                ],
                "final_answer": "NVDA is now present in your Primary watchlist.",
            }
        ]
    }
    path = tmp_path / "results.json"
    path.write_text(json.dumps(results), encoding="utf-8")
    report = score_results(fixtures, load_json(path))
    assert report["passed"] is True


def test_evaluator_rejects_unconfirmed_write_and_hallucinated_answer() -> None:
    fixtures = load_json(DEFAULT_FIXTURES)
    fixtures["cases"] = [case for case in fixtures["cases"] if case["id"] == "watchlist_requires_confirmation"]
    report = score_results(
        fixtures,
        {
            "cases": [
                {
                    "id": "watchlist_requires_confirmation",
                    "tool_calls": [
                        {
                            "tool": "update_watchlist",
                            "arguments": {"ticker": "NVDA", "action": "add", "confirmed": False},
                        }
                    ],
                    "final_answer": "I added NVDA.",
                }
            ]
        },
    )
    assert report["passed"] is False
    failures = report["cases"][0]["failures"]
    assert "forbidden tool called: update_watchlist" in failures
    assert "unconfirmed write call: update_watchlist" in failures


def test_agent_config_references_executable_fixture() -> None:
    config = (DEFAULT_FIXTURES.parent / "agent_bricks_config.yaml").read_text(encoding="utf-8")
    prompt = (DEFAULT_FIXTURES.parent / "system_prompt.md").read_text(encoding="utf-8")
    assert "contract_version: \"1.0\"" in config
    assert "fixture_file: evaluations.json" in config
    assert "exactly the nine tools in MCP contract version `1.0`" in prompt
