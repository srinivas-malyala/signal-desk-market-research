"""Measure and persist the Phase 2 one-million-row certification."""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

if __package__ in {None, ""}:
    runtime_file = globals().get("__file__") or globals().get("filename")
    if runtime_file:
        sys.path.insert(0, str(Path(runtime_file).resolve().parents[1]))

from shared.market_certification import (  # noqa: E402
    MarketCertificationMetrics,
    build_market_certification,
    max_events_in_rolling_window,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--schema", required=True)
    parser.add_argument("--volume", required=True)
    return parser.parse_args(argv)


def _scalar(frame, column: str) -> int:
    value = frame.first()[column]
    return int(value or 0)


def main(argv: list[str] | None = None) -> int:
    from pyspark.sql import SparkSession
    from pyspark.sql import functions as F

    args = parse_args(argv)
    spark = SparkSession.getActiveSession() or SparkSession.builder.getOrCreate()
    namespace = f"{args.catalog}.{args.schema}"

    manifests = spark.table(f"{namespace}.bronze_market_manifests")
    bronze = spark.table(f"{namespace}.bronze_market_daily")
    silver = spark.table(f"{namespace}.silver_market_bars")
    quarantine = spark.table(f"{namespace}.silver_market_quarantine")

    manifest_summary = manifests.agg(
        F.count("*").alias("manifest_dates"),
        F.sum("row_count").alias("manifest_rows"),
        F.sum("byte_count").alias("manifest_bytes"),
        F.sum("elapsed_ms").alias("successful_api_elapsed_ms"),
        F.min("trading_date").cast("string").alias("minimum_trading_date"),
        F.max("trading_date").cast("string").alias("maximum_trading_date"),
    ).first()
    duplicate_keys = silver.groupBy("ticker", "trading_date").count().filter(F.col("count") > 1)

    audit_path = f"/Volumes/{args.catalog}/{args.schema}/{args.volume}/_control/massive_rate_limit_audit.jsonl"
    audit_timestamps = [
        float(row["acquired_at_epoch"])
        for row in spark.read.json(audit_path).select("acquired_at_epoch").collect()
    ]
    metrics = MarketCertificationMetrics(
        api_attempts=len(audit_timestamps),
        max_attempts_in_rolling_minute=max_events_in_rolling_window(audit_timestamps),
        manifest_dates=int(manifest_summary["manifest_dates"] or 0),
        manifest_rows=int(manifest_summary["manifest_rows"] or 0),
        manifest_bytes=int(manifest_summary["manifest_bytes"] or 0),
        successful_api_elapsed_ms=int(manifest_summary["successful_api_elapsed_ms"] or 0),
        bronze_rows=_scalar(bronze.agg(F.count("*").alias("count")), "count"),
        silver_rows=_scalar(silver.agg(F.count("*").alias("count")), "count"),
        quarantine_rows=_scalar(quarantine.agg(F.count("*").alias("count")), "count"),
        silver_distinct_keys=_scalar(
            silver.select("ticker", "trading_date").distinct().agg(F.count("*").alias("count")),
            "count",
        ),
        duplicate_silver_keys=_scalar(duplicate_keys.agg(F.count("*").alias("count")), "count"),
        minimum_trading_date=manifest_summary["minimum_trading_date"],
        maximum_trading_date=manifest_summary["maximum_trading_date"],
    )
    report = build_market_certification(metrics)
    report_row = {
        "certification_id": str(uuid.uuid4()),
        "certified_at": report["certified_at"],
        "status": report["status"],
        "report_json": json.dumps(report, separators=(",", ":"), sort_keys=True),
    }
    spark.createDataFrame([report_row]).write.mode("append").saveAsTable(
        f"{namespace}.market_volume_certifications"
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
