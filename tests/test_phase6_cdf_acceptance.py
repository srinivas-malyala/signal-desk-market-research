from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_phase6_cdf_acceptance_is_bounded_and_cleans_every_operational_row() -> None:
    source = (ROOT / "tools" / "phase6_cdf_acceptance.py").read_text(encoding="utf-8")
    ast.parse(source)

    for table in (
        "watchlist_tickers",
        "research_notes",
        "analysis_reports",
        "agent_sessions",
        "agent_tool_events",
    ):
        assert f'"{table}"' in source
    assert 'cursor.execute(f"DELETE FROM {tables[\'agent_tool_events\']}' in source
    assert 'cursor.execute(f"DELETE FROM {tables[\'users\']}' in source
    assert "connection.commit()" in source
    assert "connection.rollback()" in source
    assert '"cleanup_complete": cleanup_complete' in source
    assert "str(session_id)" in source
    assert 'os.environ["DATABRICKS_CONFIG_PROFILE"] = args.profile' in source
