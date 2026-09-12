from __future__ import annotations

from datetime import date

from tools.phase5_retrieval_acceptance import GOVERNED_SOURCE, evaluate_retrieval


def _rows() -> list[dict]:
    return [
        {"date": "2026-09-01", "open": 99.0, "high": 101.0, "low": 98.0, "close": 100.0},
        {"date": "2026-09-10", "open": 100.0, "high": 111.0, "low": 99.0, "close": 110.0},
    ]


def test_acceptance_passes_governed_known_answer_and_safe_entitlement() -> None:
    rows = _rows()
    result = evaluate_retrieval(
        {
            "status": "success",
            "ticker": "AAPL",
            "source": GOVERNED_SOURCE,
            "as_of": "2026-09-10",
            "daily_bars": rows,
            "change_percent": 10.0,
            "current_snapshot": {
                "available": False,
                "message": "Endpoint is not included in this subscription.",
                "fallback": "latest daily aggregate",
            },
        },
        rows,
        today=date(2026, 9, 11),
        max_staleness_days=7,
        massive_attempts=1,
    )
    assert result["status"] == "passed"
    assert all(check["passed"] for check in result["checks"])


def test_acceptance_rejects_massive_history_fallback_and_stale_data() -> None:
    rows = _rows()
    result = evaluate_retrieval(
        {
            "status": "success",
            "ticker": "AAPL",
            "source": "Massive Stocks API daily aggregates",
            "as_of": "2026-09-01",
            "daily_bars": rows,
            "change_percent": 10.0,
            "current_snapshot": {"available": True, "price": 110.0},
        },
        rows,
        today=date(2026, 9, 11),
        max_staleness_days=3,
        massive_attempts=5,
    )
    assert result["status"] == "failed"
    failed = {check["name"] for check in result["checks"] if not check["passed"]}
    assert failed == {"governed_history_preferred", "freshness", "massive_free_plan_budget"}
