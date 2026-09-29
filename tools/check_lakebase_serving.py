"""Return sanitized reconciliation evidence for Signal Desk Lakebase serving tables."""

from __future__ import annotations

import argparse
import base64
import json

import psycopg2
from databricks.sdk import WorkspaceClient
from psycopg2.extras import RealDictCursor


def check(profile: str, secret_scope: str, secret_key: str) -> dict:
    secret = WorkspaceClient(profile=profile).secrets.get_secret(scope=secret_scope, key=secret_key)
    dsn = base64.b64decode(secret.value).decode("utf-8")
    connection = psycopg2.connect(dsn, connect_timeout=10, cursor_factory=RealDictCursor)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT count(*) AS count,
                          count(*) - count(DISTINCT (ticker, trading_date)) AS duplicate_keys,
                          min(trading_date)::text AS min_date,
                          max(trading_date)::text AS max_date
                   FROM bootcamp_students.market_history_serving_srini"""
            )
            market = dict(cursor.fetchone())
            cursor.execute(
                """SELECT ticker, trading_date::text AS trading_date, open, high, low, close,
                          daily_return, annualized_volatility_20d, source_request_id,
                          source_freshness_at::text AS source_freshness_at
                   FROM bootcamp_students.market_history_serving_srini
                   WHERE ticker='AAPL'
                   ORDER BY trading_date DESC
                   LIMIT 3"""
            )
            aapl = [dict(row) for row in cursor.fetchall()]
            cursor.execute(
                """SELECT count(*) AS count,
                          count(*) - count(DISTINCT chunk_id) AS duplicate_keys
                   FROM bootcamp_students.research_documents_serving_srini"""
            )
            research = dict(cursor.fetchone())
            cursor.execute(
                """SELECT indexname FROM pg_indexes
                   WHERE schemaname='bootcamp_students'
                     AND tablename IN (
                       'market_history_serving_srini', 'research_documents_serving_srini'
                     )
                   ORDER BY indexname"""
            )
            indexes = [row["indexname"] for row in cursor.fetchall()]
        return {"market": market, "research": research, "aapl_latest": aapl, "indexes": indexes}
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--secret-scope", default="database")
    parser.add_argument("--secret-key", default="lakebase-url")
    args = parser.parse_args()
    print(json.dumps(check(args.profile, args.secret_scope, args.secret_key), default=str, sort_keys=True))
    return 0


if __name__ == "__main__":
    main()
