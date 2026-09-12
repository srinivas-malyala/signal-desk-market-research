from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from jobs.publish_research_search_documents import publish_sql  # noqa: E402


def test_publish_sql_creates_cdf_table_and_incrementally_merges() -> None:
    create, properties, merge = publish_sql("bootcamp_students", "student_sri")

    assert "CREATE TABLE IF NOT EXISTS `bootcamp_students`.`student_sri`.`research_search_documents`" in create
    assert "delta.enableChangeDataFeed" in create
    assert "delta.enableRowTracking" in properties
    assert "USING `bootcamp_students`.`student_sri`.`silver_research_chunks`" in merge
    assert "target.chunk_id = source.chunk_id" in merge
    assert "THEN UPDATE SET *" in merge
    assert "WHEN NOT MATCHED THEN INSERT *" in merge
    assert "WHEN NOT MATCHED BY SOURCE THEN DELETE" in merge


def test_publish_sql_rejects_untrusted_identifiers() -> None:
    with pytest.raises(ValueError, match="simple SQL identifiers"):
        publish_sql("bootcamp_students; DROP CATALOG main", "student_sri")
