from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESOURCES = ROOT / "resources"


def test_activity_analytics_refresh_matches_frontend_freshness_contract() -> None:
    resource = (RESOURCES / "activity_analytics_refresh.job.yml").read_text(encoding="utf-8")

    assert 'quartz_cron_expression: "0 0/30 * * * ?"' in resource
    assert "pause_status: UNPAUSED" in resource
    assert "${resources.pipelines.activity_analytics_pipeline.id}" in resource
    assert "full_refresh: false" in resource


def test_market_daily_refresh_publishes_only_market_serving_data() -> None:
    resource = (RESOURCES / "market_daily_refresh.job.yml").read_text(encoding="utf-8")

    ordered_steps = (
        "land_recent_market_data",
        "refresh_market_pipeline",
        "publish_market_delta_serving",
        "publish_market_lakebase_serving",
    )
    positions = [resource.index(step) for step in ordered_steps]
    assert positions == sorted(positions)
    assert 'quartz_cron_expression: "0 0 6 ? * MON-FRI"' in resource
    assert "timezone_id: America/Los_Angeles" in resource
    assert "resources.jobs.market_ingestion.id" in resource
    assert "resources.pipelines.market_pipeline.id" in resource
    assert "resources.jobs.market_serving_publish.id" in resource
    assert "resources.jobs.lakebase_serving_publish.id" in resource
    assert "dataset: market" in resource


def test_research_refresh_runs_every_six_hours() -> None:
    resource = (RESOURCES / "research_refresh.job.yml").read_text(encoding="utf-8")

    assert "pause_status: UNPAUSED" in resource
    assert "interval: 6" in resource
    assert "unit: HOURS" in resource


def test_historical_market_backfill_remains_manual() -> None:
    resource = (RESOURCES / "market_volume_backfill.job.yml").read_text(encoding="utf-8")

    assert "schedule:" not in resource
    assert "trigger:" not in resource
    assert "continuous:" not in resource
