"""Create non-destructive Signal Desk serving tables in the shared Lakebase schema."""

from __future__ import annotations

import argparse
import base64
import json
import re

import psycopg2
from databricks.sdk import WorkspaceClient
from psycopg2 import sql
from psycopg2.extras import RealDictCursor

IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]*$")


def identifier(value: str, label: str) -> str:
    if not IDENTIFIER.fullmatch(value):
        raise ValueError(f"{label} must be a lowercase PostgreSQL identifier")
    return value


def table_names(suffix: str) -> tuple[str, str]:
    clean_suffix = identifier(suffix, "suffix")
    return f"market_history_serving_{clean_suffix}", f"research_documents_serving_{clean_suffix}"


def setup(profile: str, secret_scope: str, secret_key: str, schema: str, suffix: str) -> dict:
    clean_schema = identifier(schema, "schema")
    market_table, research_table = table_names(suffix)
    secret = WorkspaceClient(profile=profile).secrets.get_secret(scope=secret_scope, key=secret_key)
    dsn = base64.b64decode(secret.value).decode("utf-8")
    connection = psycopg2.connect(dsn, connect_timeout=10, cursor_factory=RealDictCursor)
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_namespace WHERE nspname=%s", (clean_schema,))
            if cursor.fetchone() is None:
                raise RuntimeError(f"Required shared Lakebase schema does not exist: {clean_schema}")
            cursor.execute(
                sql.SQL(
                    """CREATE TABLE IF NOT EXISTS {}.{} (
                        ticker TEXT NOT NULL,
                        trading_date DATE NOT NULL,
                        open DOUBLE PRECISION,
                        high DOUBLE PRECISION,
                        low DOUBLE PRECISION,
                        close DOUBLE PRECISION,
                        vwap DOUBLE PRECISION,
                        volume DOUBLE PRECISION,
                        transactions BIGINT,
                        daily_return DOUBLE PRECISION,
                        annualized_volatility_20d DOUBLE PRECISION,
                        source_request_id TEXT,
                        source_freshness_at TIMESTAMPTZ,
                        serving_content_hash TEXT NOT NULL,
                        PRIMARY KEY (ticker, trading_date)
                    )"""
                ).format(sql.Identifier(clean_schema), sql.Identifier(market_table))
            )
            cursor.execute(
                sql.SQL("CREATE INDEX IF NOT EXISTS {} ON {}.{} (ticker, trading_date DESC)").format(
                    sql.Identifier(f"idx_market_history_serving_{suffix}"),
                    sql.Identifier(clean_schema),
                    sql.Identifier(market_table),
                )
            )
            cursor.execute(
                sql.SQL(
                    """CREATE TABLE IF NOT EXISTS {}.{} (
                        chunk_id TEXT PRIMARY KEY,
                        parent_id TEXT,
                        source_type TEXT NOT NULL,
                        source_id TEXT NOT NULL,
                        tickers_text TEXT NOT NULL DEFAULT '',
                        ticker TEXT,
                        title TEXT,
                        source_date DATE,
                        source_url TEXT,
                        fetched_at TIMESTAMPTZ,
                        section_name TEXT,
                        chunk_index INTEGER NOT NULL,
                        chunk_to_retrieve TEXT NOT NULL,
                        chunk_token_count INTEGER,
                        parent_text TEXT,
                        parent_token_count INTEGER,
                        source_content_hash TEXT NOT NULL
                    )"""
                ).format(sql.Identifier(clean_schema), sql.Identifier(research_table))
            )
            cursor.execute(
                sql.SQL(
                    """CREATE INDEX IF NOT EXISTS {} ON {}.{}
                    USING gin (to_tsvector('english', coalesce(title,'') || ' ' || coalesce(chunk_to_retrieve,'')))"""
                ).format(
                    sql.Identifier(f"idx_research_documents_fts_{suffix}"),
                    sql.Identifier(clean_schema),
                    sql.Identifier(research_table),
                )
            )
            cursor.execute(
                sql.SQL("CREATE INDEX IF NOT EXISTS {} ON {}.{} (ticker, source_date DESC)").format(
                    sql.Identifier(f"idx_research_documents_ticker_{suffix}"),
                    sql.Identifier(clean_schema),
                    sql.Identifier(research_table),
                )
            )
            connection.commit()
            counts = {}
            for name in (market_table, research_table):
                cursor.execute(
                    sql.SQL("SELECT count(*) AS count FROM {}.{}").format(
                        sql.Identifier(clean_schema), sql.Identifier(name)
                    )
                )
                counts[name] = int(cursor.fetchone()["count"])
            return {"schema": clean_schema, "tables": counts}
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--secret-scope", default="database")
    parser.add_argument("--secret-key", default="lakebase-url")
    parser.add_argument("--schema", default="bootcamp_students")
    parser.add_argument("--suffix", default="srini")
    args = parser.parse_args()
    print(
        json.dumps(
            setup(args.profile, args.secret_scope, args.secret_key, args.schema, args.suffix),
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    main()
