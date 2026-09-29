"""Bounded read adapters for Lakebase-hosted MCP serving copies."""

from __future__ import annotations

import os
import re
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import lakebase
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]*$")
SOURCE_TYPES = frozenset({"filing", "article"})
NUMERIC_FIELDS = frozenset(
    {
        "open",
        "high",
        "low",
        "close",
        "vwap",
        "volume",
        "transactions",
        "daily_return",
        "annualized_volatility_20d",
        "score",
    }
)

_serving_pool: pool.ThreadedConnectionPool | None = None


def _identifier(value: str, setting: str) -> str:
    if not IDENTIFIER.fullmatch(value):
        raise ValueError(f"{setting} must be a lowercase PostgreSQL identifier")
    return value


def serving_schema() -> str:
    return _identifier(
        os.getenv("SIGNAL_DESK_SERVING_SCHEMA", "bootcamp_students"),
        "SIGNAL_DESK_SERVING_SCHEMA",
    )


def serving_table(setting: str, default: str) -> str:
    table = _identifier(os.getenv(setting, default), setting)
    return f"{serving_schema()}.{table}"


def market_backend() -> str:
    backend = os.getenv("SIGNAL_DESK_MARKET_BACKEND", "databricks").strip().casefold()
    if backend not in {"databricks", "lakebase"}:
        raise ValueError("SIGNAL_DESK_MARKET_BACKEND must be databricks or lakebase")
    return backend


def research_backend() -> str:
    backend = os.getenv("SIGNAL_DESK_RESEARCH_BACKEND", "databricks").strip().casefold()
    if backend not in {"databricks", "lakebase_fts", "lakebase_pgvector"}:
        raise ValueError(
            "SIGNAL_DESK_RESEARCH_BACKEND must be databricks, lakebase_fts, or lakebase_pgvector"
        )
    if backend == "lakebase_pgvector":
        raise RuntimeError("lakebase_pgvector is reserved until its quality and runtime gates pass")
    return backend


def _get_serving_pool() -> pool.ThreadedConnectionPool:
    global _serving_pool
    if _serving_pool is None:
        dsn = os.getenv("LAKEBASE_SERVING_URL") or lakebase.get_lakebase_url()
        _serving_pool = pool.ThreadedConnectionPool(
            1,
            int(os.getenv("LAKEBASE_SERVING_POOL_MAX", "5")),
            dsn=dsn,
            cursor_factory=RealDictCursor,
            connect_timeout=10,
            application_name="signal-desk-serving",
        )
    return _serving_pool


@contextmanager
def serving_connection():
    connection_pool = _get_serving_pool()
    connection = connection_pool.getconn()
    try:
        yield connection
    except Exception:
        connection.rollback()
        raise
    finally:
        connection_pool.putconn(connection, close=bool(connection.closed))


def close_serving_pool() -> None:
    global _serving_pool
    if _serving_pool is not None:
        _serving_pool.closeall()
        _serving_pool = None


def _normalized(row: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(row)
    for field in NUMERIC_FIELDS:
        if normalized.get(field) is not None and isinstance(normalized[field], (Decimal, int, float)):
            normalized[field] = float(normalized[field])
    for field in ("date", "source_date"):
        if isinstance(normalized.get(field), (date, datetime)):
            normalized[field] = normalized[field].isoformat()[:10]
    for field in ("fetched_at", "source_freshness_at"):
        if isinstance(normalized.get(field), datetime):
            normalized[field] = normalized[field].isoformat()
    return normalized


def fetch_market_bars(
    ticker: str,
    start_date: str,
    end_date: str,
    *,
    connection=None,
) -> list[dict[str, Any]]:
    """Read a single bounded ticker/date window from the Lakebase serving copy."""

    table = serving_table("SIGNAL_DESK_MARKET_SERVING_TABLE", "market_history_serving_srini")
    sql = f"""SELECT trading_date AS date, open, high, low, close, vwap, volume,
              transactions, daily_return, annualized_volatility_20d,
              source_request_id, source_freshness_at
        FROM {table}
        WHERE ticker=%s AND trading_date BETWEEN %s AND %s
        ORDER BY trading_date
        LIMIT 370"""

    def run(active_connection) -> list[dict[str, Any]]:
        with active_connection.cursor() as cursor:
            cursor.execute(sql, (ticker, start_date, end_date))
            return [_normalized(dict(row)) for row in cursor.fetchall()]

    if connection is not None:
        return run(connection)
    with serving_connection() as active_connection:
        return run(active_connection)


def _iso_date(value: str | date | datetime | None, field_name: str) -> str | None:
    if value is None or value == "":
        return None
    try:
        return date.fromisoformat(str(value)[:10]).isoformat()
    except ValueError as error:
        raise ValueError(f"{field_name} must be an ISO date (YYYY-MM-DD).") from error


class LakebaseResearchSearch:
    """PostgreSQL full-text candidate search with bounded provenance results."""

    def __init__(self, connection=None) -> None:
        self.connection = connection

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        tickers: list[str] | None = None,
        source_types: list[str] | None = None,
        start_date: str | date | None = None,
        end_date: str | date | None = None,
    ) -> dict[str, Any]:
        text = (query or "").strip()
        if not text:
            raise ValueError("A non-empty research query is required.")
        limit = min(max(int(top_k), 1), 5)
        candidate_limit = min(max(limit * 4, 20), 50)
        symbols = sorted({str(value).strip().upper() for value in tickers or [] if str(value).strip()})
        types = sorted({str(value).strip().casefold() for value in source_types or [] if str(value).strip()})
        unsupported = sorted(set(types) - SOURCE_TYPES)
        if unsupported:
            raise ValueError(f"Unsupported source type(s): {', '.join(unsupported)}")
        start = _iso_date(start_date, "start_date")
        end = _iso_date(end_date, "end_date")
        if start and end and start > end:
            raise ValueError("start_date must be on or before end_date.")

        table = serving_table("SIGNAL_DESK_RESEARCH_SERVING_TABLE", "research_documents_serving_srini")
        vector = "to_tsvector('english', coalesce(title,'') || ' ' || coalesce(chunk_to_retrieve,''))"
        predicates = [f"{vector} @@ websearch_to_tsquery('english', %s)"]
        predicate_params: list[Any] = [text]
        if symbols:
            predicates.append(
                "(ticker = ANY(%s) OR EXISTS (SELECT 1 FROM unnest(%s::text[]) AS requested(symbol) "
                "WHERE position('|' || requested.symbol || '|' IN tickers_text) > 0))"
            )
            predicate_params.extend((symbols, symbols))
        if types:
            predicates.append("source_type = ANY(%s)")
            predicate_params.append(types)
        if start:
            predicates.append("source_date >= %s")
            predicate_params.append(start)
        if end:
            predicates.append("source_date <= %s")
            predicate_params.append(end)
        params = [text, *predicate_params, candidate_limit]
        sql = f"""SELECT chunk_id, parent_id, source_type, source_id,
                   string_to_array(trim(both '|' from tickers_text), '|') AS tickers, ticker,
                   title, source_date, source_url, fetched_at, section_name, chunk_index,
                   chunk_to_retrieve AS passage, chunk_token_count,
                   parent_text AS context, parent_token_count, source_content_hash,
                   ts_rank_cd({vector}, websearch_to_tsquery('english', %s)) AS score
            FROM {table}
            WHERE {' AND '.join(predicates)}
            ORDER BY score DESC, source_date DESC NULLS LAST, chunk_id
            LIMIT %s"""

        def run(active_connection) -> list[dict[str, Any]]:
            with active_connection.cursor() as cursor:
                cursor.execute(sql, tuple(params))
                return [_normalized(dict(row)) for row in cursor.fetchall()]

        if self.connection is not None:
            candidates = run(self.connection)
        else:
            with serving_connection() as active_connection:
                candidates = run(active_connection)

        matches: list[dict[str, Any]] = []
        seen_parents: set[str] = set()
        for row in candidates:
            parent_key = str(row.get("parent_id") or row.get("chunk_id"))
            if parent_key in seen_parents:
                continue
            seen_parents.add(parent_key)
            matches.append(row)
            if len(matches) == limit:
                break
        filters = {
            key: value
            for key, value in {
                "tickers": symbols or None,
                "source_type": types or None,
                "source_date >=": start,
                "source_date <=": end,
            }.items()
            if value is not None
        }
        return {
            "status": "success",
            "contract_version": "1.0",
            "query": text,
            "matches": matches,
            "count": len(matches),
            "retrieval": {
                "backend": "lakebase_fts",
                "query_type": "POSTGRES_FULL_TEXT",
                "candidate_limit": candidate_limit,
                "result_limit": limit,
                "filters": filters,
            },
            "limitations": [
                "This backend uses lexical PostgreSQL full-text ranking and is not a semantic embedding search.",
                "Promotion requires the committed 51-case quality and provenance thresholds to pass.",
            ],
        }
