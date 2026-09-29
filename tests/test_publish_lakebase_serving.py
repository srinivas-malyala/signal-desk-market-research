from __future__ import annotations

import pytest

from jobs.publish_lakebase_serving import research_source_sql, serving_tables


def test_shared_lakebase_targets_follow_student_suffix() -> None:
    assert serving_tables("srini") == (
        "market_history_serving_srini",
        "research_documents_serving_srini",
    )


def test_research_projection_flattens_tickers_without_json_extensions() -> None:
    statement = research_source_sql("bootcamp_students", "student_sri")
    assert "research_search_documents" in statement
    assert "tickers_text" in statement
    assert "concat_ws" in statement
    assert "source_content_hash" in statement


def test_publisher_rejects_unsafe_identifiers() -> None:
    with pytest.raises(ValueError, match="lowercase SQL identifier"):
        serving_tables("srini;drop")
