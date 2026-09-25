from __future__ import annotations

import ast
import json
from pathlib import Path

from shared.activity_analytics import build_gold_metrics, normalize_change_events, silver_agent_activity

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "fixtures" / "cdc" / "phase6_activity_events.json"
PIPELINES = ROOT / "pipelines"


def _fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _metric_map(rows: list[dict], *keys: str) -> dict[tuple, dict]:
    return {tuple(row[key] for key in keys): row for row in rows}


def test_synthetic_cdc_normalizes_safe_fields_and_quarantines_invalid_event() -> None:
    fixture = _fixture()
    normalized, quarantined = normalize_change_events(fixture["events"])

    assert len(normalized) == 14
    assert quarantined == [
        {"position": 14, "source_table": "agent_tool_events", "reason": "ordering metadata is missing"}
    ]
    assert {row["source_table"] for row in normalized} == {
        "agent_tool_events",
        "agent_sessions",
        "watchlist_tickers",
        "research_notes",
        "analysis_reports",
    }
    rendered = json.dumps(normalized)
    assert "@example.test" not in rendered
    assert "private-note-sentinel" not in rendered
    assert "private-report-sentinel" not in rendered
    assert "private-thesis-sentinel" not in rendered
    assert all(
        row["user_pseudonym"] is None or len(row["user_pseudonym"]) == 64
        for row in normalized
    )


def test_silver_handles_duplicates_preimages_deletes_and_late_events() -> None:
    normalized, _ = normalize_change_events(_fixture()["events"])
    silver = silver_agent_activity(normalized)

    assert len(silver) == 11
    assert all(row["change_type"] != "update_preimage" for row in silver)
    assert len({row["change_id"] for row in silver}) == len(silver)
    assert any(row["change_type"] == "delete" for row in silver)
    late = next(row for row in silver if row["record_key"] == "101")
    assert late["activity_date"] == "2026-09-10"
    assert late["source_latency_seconds"] == 240
    watchlist_delete = next(
        row
        for row in silver
        if row["source_table"] == "watchlist_tickers" and row["change_type"] == "delete"
    )
    assert watchlist_delete["event_timestamp"] == "2026-09-11T00:10:00+00:00"


def test_gold_metrics_reconcile_to_known_synthetic_sequence() -> None:
    fixture = _fixture()
    normalized, _ = normalize_change_events(fixture["events"])
    metrics = build_gold_metrics(
        silver_agent_activity(normalized),
        refreshed_at=fixture["refreshed_at"],
    )

    active = _metric_map(metrics["daily_active_researchers"], "activity_date")
    assert active[("2026-09-10",)]["daily_active_researchers"] == 1
    assert active[("2026-09-10",)]["agent_invocations"] == 1
    assert active[("2026-09-11",)]["daily_active_researchers"] == 2
    assert active[("2026-09-11",)]["agent_invocations"] == 3

    errors = _metric_map(metrics["agent_error_rate"], "activity_date")
    assert errors[("2026-09-10",)]["error_rate"] == 0.0
    assert errors[("2026-09-11",)]["error_count"] == 1
    assert errors[("2026-09-11",)]["error_rate"] == 0.3333

    tools = _metric_map(metrics["tool_usage_latency"], "activity_date", "tool_name")
    semantic = tools[("2026-09-11", "semantic_research")]
    assert semantic["invocation_count"] == 1
    assert semantic["error_count"] == 1
    assert semantic["null_duration_count"] == 1
    assert semantic["average_duration_ms"] is None
    performance = tools[("2026-09-10", "get_stock_performance")]
    assert performance["p50_duration_ms"] == 100
    assert performance["p95_duration_ms"] == 100

    watchlist = _metric_map(metrics["watchlist_changes"], "activity_date", "action_type")
    assert watchlist[("2026-09-11", "create")]["change_count"] == 1
    assert watchlist[("2026-09-11", "delete")]["change_count"] == 1

    saves = _metric_map(metrics["research_saves"], "activity_date", "research_type", "action_type")
    assert saves[("2026-09-11", "note", "create")]["change_count"] == 1
    assert saves[("2026-09-11", "note", "update")]["change_count"] == 1
    assert saves[("2026-09-11", "note", "delete")]["change_count"] == 1
    assert saves[("2026-09-11", "report", "create")]["change_count"] == 1
    for family in metrics.values():
        assert all(row["metric_source"].startswith("silver_agent_activity:") for row in family)
        assert all(row["source_max_synced_at"] for row in family)
        assert all(row["metric_refreshed_at"] == fixture["refreshed_at"] for row in family)


def test_pipeline_uses_modern_streaming_append_flows_and_materialized_views() -> None:
    bronze = (PIPELINES / "bronze_lakebase_changes.py").read_text(encoding="utf-8")
    silver = (PIPELINES / "silver_agent_activity.py").read_text(encoding="utf-8")
    ast.parse(bronze)
    ast.parse(silver)

    assert "from pyspark import pipelines as dp" in bronze
    assert 'dp.create_streaming_table(' in bronze
    assert bronze.count('@dp.append_flow(target="bronze_lakebase_changes"') == 5
    assert bronze.count("spark.readStream.table") == 5
    assert "import dlt" not in bronze
    for prohibited in ("user_email", "note_text", "report_text", "thesis", "source_context", "idempotency_key"):
        assert prohibited not in bronze
    assert "@dp.materialized_view(" in silver
    assert 'spark.read.table("bronze_lakebase_changes")' in silver
    assert 'Window.partitionBy("change_id")' in silver
    assert 'F.col("change_type").isin("insert", "update_postimage", "delete")' in silver


def test_gold_pipeline_contracts_preserve_freshness_and_never_select_authored_text() -> None:
    gold_files = {
        "gold_daily_active_researchers.py",
        "gold_tool_usage_latency.py",
        "gold_agent_error_rate.py",
        "gold_watchlist_changes.py",
        "gold_research_saves.py",
    }
    for filename in gold_files:
        source = (PIPELINES / filename).read_text(encoding="utf-8")
        ast.parse(source)
        assert "@dp.materialized_view(" in source
        assert 'spark.read.table("silver_agent_activity")' in source
        assert "source_max_synced_at" in source
        assert "metric_refreshed_at" in source
        assert "metric_source" in source
        assert "note_text" not in source
        assert "report_text" not in source
        assert "user_email" not in source


def test_bundle_registers_parameterized_activity_analytics_pipeline() -> None:
    resource = (ROOT / "resources" / "activity_analytics.pipeline.yml").read_text(encoding="utf-8")
    bundle = (ROOT / "databricks.yml").read_text(encoding="utf-8")

    assert "activity_lkbase" not in resource
    assert "serverless: true" in resource
    assert "${var.catalog}" in resource
    assert "${var.schema}" in resource
    assert "signal_desk.cdc_source_catalog: ${var.cdc_source_catalog}" in resource
    assert "signal_desk.cdc_source_schema: ${var.cdc_source_schema}" in resource
    assert "${var.lakebase_table_suffix}" in resource
    assert "lakebase_table_suffix:" in bundle
    assert "cdc_source_catalog: bootcamp_students" in bundle
    assert "cdc_source_schema: bootcamp_cdc" in bundle
    for filename in (
        "bronze_lakebase_changes.py",
        "silver_agent_activity.py",
        "gold_daily_active_researchers.py",
        "gold_tool_usage_latency.py",
        "gold_agent_error_rate.py",
        "gold_watchlist_changes.py",
        "gold_research_saves.py",
    ):
        assert filename in resource
