# ADR 0003: Data and pipeline design

- Status: Accepted
- Date: 2026-09-10

## Decision

- Land Massive and SEC responses immutably in a Unity Catalog Volume with checksums and manifests.
- Use Python Lakeflow Spark Declarative Pipelines because later phases require parameterized parsing and PySpark tests.
- Use Auto Loader and a streaming table for incremental Bronze file ingestion.
- Use a streaming Silver table for normalized append-oriented facts and materialized views for Gold aggregations.
- Preserve source request ID, source path, event date, ingestion time, and rescued data for lineage.
- Use Massive's grouped daily market endpoint at four requests per rolling minute. Stop only after Silver contains more than one million distinct `(ticker, trading_date)` rows.
- Use SEC submissions, Company Facts, and selected filing documents to satisfy high variety with authoritative structured and unstructured data.
- Prefer Lakebase Lakehouse Sync/change capture for operational analytics when available. Because its setup is workspace/UI dependent, retain a Lakeflow-managed append-only agent-event table as the approved rubric-compatible fallback.

## Consequences

The market backfill is slow but deterministic and remains below the documented five-calls-per-minute free allowance. The feasibility spike must measure actual grouped-response row counts before projecting duration.
