from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from jobs.publish_market_serving import publish_sql, serving_source_sql  # noqa: E402


def test_market_serving_sql_is_narrow_cdf_enabled_and_incremental() -> None:
    source = serving_source_sql("bootcamp_students", "student_sri")
    create, properties, merge = publish_sql("bootcamp_students", "student_sri")

    assert "silver_market_bars" in source
    assert "gold_stock_performance" in source
    assert "source_freshness_at" in source
    assert "serving_content_hash" in source
    assert "CREATE TABLE IF NOT EXISTS `bootcamp_students`.`student_sri`.`market_history_serving`" in create
    assert "delta.enableChangeDataFeed" in create
    assert "delta.enableRowTracking" in properties
    assert "target.ticker = source.ticker" in merge
    assert "target.trading_date = source.trading_date" in merge
    assert "target.serving_content_hash <=> source.serving_content_hash" in merge
    assert "WHEN NOT MATCHED BY SOURCE THEN DELETE" in merge


def test_market_serving_sql_rejects_untrusted_identifiers() -> None:
    with pytest.raises(ValueError, match="simple SQL identifiers"):
        publish_sql("bootcamp_students", "student_sri; DROP SCHEMA public")


def test_market_serving_serverless_entrypoint_does_not_raise_system_exit() -> None:
    script = (ROOT / "jobs" / "publish_market_serving.py").read_text()
    assert "raise SystemExit" not in script
