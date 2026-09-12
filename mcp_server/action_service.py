"""Transactional, confirmed, idempotent Lakebase actions."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from typing import Any

import lakebase
from psycopg2.extras import Json

IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")


def _table(base: str) -> str:
    return lakebase.table_name(base)


def _identity_email(email: str) -> str:
    normalized = (email or "").strip().lower()
    if "@" not in normalized or len(normalized) > 320:
        raise ValueError("A valid trusted user identity is required.")
    return normalized


def _fingerprint(value: dict[str, Any]) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _execute(
    user_email: str,
    operation_name: str,
    idempotency_key: str | None,
    confirmed: bool,
    action: Callable[[Any, int], dict[str, Any]],
    request_fingerprint: str | None = None,
) -> dict[str, Any]:
    if confirmed is not True:
        raise ValueError("Explicit confirmation is required for this write.")
    key = (idempotency_key or "").strip()
    if not IDEMPOTENCY_KEY.fullmatch(key):
        raise ValueError("idempotency_key must be 8-128 safe characters.")
    email = _identity_email(user_email)
    with lakebase.get_connection() as connection, connection.cursor() as cursor:
        try:
            cursor.execute(
                f"INSERT INTO {_table('users')}(email) VALUES(%s) "
                "ON CONFLICT(email) DO UPDATE SET updated_at=now() RETURNING id",
                (email,),
            )
            user_id = cursor.fetchone()["id"]
            cursor.execute(
                f"""INSERT INTO {_table('idempotency_records')}(user_id,operation_name,idempotency_key,result)
                VALUES(%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING idempotency_key""",
                (
                    user_id,
                    operation_name,
                    key,
                    Json({"status": "pending", "_request_fingerprint": request_fingerprint}),
                ),
            )
            if cursor.fetchone() is None:
                cursor.execute(
                    f"""SELECT result FROM {_table('idempotency_records')}
                    WHERE user_id=%s AND operation_name=%s AND idempotency_key=%s""",
                    (user_id, operation_name, key),
                )
                replay = dict(cursor.fetchone()["result"])
                recorded_fingerprint = replay.pop("_request_fingerprint", None)
                if recorded_fingerprint and recorded_fingerprint != request_fingerprint:
                    raise ValueError("idempotency_key was already used for different request parameters.")
                replay["idempotent_replay"] = True
                connection.commit()
                return replay
            result = action(cursor, user_id)
            stored = {**result, "idempotent_replay": False}
            stored_record = {**stored, "_request_fingerprint": request_fingerprint}
            cursor.execute(
                f"""UPDATE {_table('idempotency_records')} SET result=%s
                WHERE user_id=%s AND operation_name=%s AND idempotency_key=%s""",
                (Json(stored_record), user_id, operation_name, key),
            )
            connection.commit()
            return stored
        except Exception:
            connection.rollback()
            raise


def update_watchlist(
    user_email: str,
    ticker: str,
    action: str,
    watchlist_name: str,
    *,
    confirmed: bool,
    idempotency_key: str | None,
) -> dict[str, Any]:
    def apply(cursor, user_id: int) -> dict[str, Any]:
        cursor.execute(
            f"""INSERT INTO {_table('watchlists')}(user_id,name,is_default) VALUES(%s,%s,true)
            ON CONFLICT(user_id,name) DO UPDATE SET name=excluded.name RETURNING id""",
            (user_id, watchlist_name),
        )
        watchlist_id = cursor.fetchone()["id"]
        if action == "add":
            cursor.execute(
                f"""INSERT INTO {_table('watchlist_tickers')}(watchlist_id,ticker)
                VALUES(%s,%s) ON CONFLICT DO NOTHING""",
                (watchlist_id, ticker),
            )
        else:
            cursor.execute(
                f"DELETE FROM {_table('watchlist_tickers')} WHERE watchlist_id=%s AND ticker=%s",
                (watchlist_id, ticker),
            )
        changed = cursor.rowcount
        cursor.execute(
            f"SELECT ticker,added_at FROM {_table('watchlist_tickers')} WHERE watchlist_id=%s ORDER BY added_at",
            (watchlist_id,),
        )
        return {
            "status": "success",
            "contract_version": "1.0",
            "watchlist": watchlist_name,
            "action": action,
            "ticker": ticker,
            "changed": bool(changed),
            "tickers": [dict(row) for row in cursor.fetchall()],
        }

    return _execute(
        user_email,
        "update_watchlist",
        idempotency_key,
        confirmed,
        apply,
        _fingerprint({"ticker": ticker, "action": action, "watchlist_name": watchlist_name}),
    )


def save_research_note(
    user_email: str,
    ticker: str,
    title: str,
    note_text: str,
    thesis_tags: list[str],
    *,
    confirmed: bool,
    idempotency_key: str | None,
) -> dict[str, Any]:
    def apply(cursor, user_id: int) -> dict[str, Any]:
        cursor.execute(
            f"""INSERT INTO {_table('research_notes')}(user_id,ticker,title,note_text,thesis_tags)
            VALUES(%s,%s,%s,%s,%s) RETURNING id,created_at""",
            (user_id, ticker, title, note_text, Json(thesis_tags)),
        )
        row = cursor.fetchone()
        return {
            "status": "success",
            "contract_version": "1.0",
            "note_id": row["id"],
            "ticker": ticker,
            "created_at": row["created_at"],
        }

    return _execute(
        user_email,
        "save_research_note",
        idempotency_key,
        confirmed,
        apply,
        _fingerprint({"ticker": ticker, "title": title, "note_text": note_text, "thesis_tags": thesis_tags}),
    )


def save_analysis_report(
    user_email: str,
    title: str,
    thesis: str,
    tickers: list[str],
    report_text: str,
    source_context: dict[str, Any],
    *,
    confirmed: bool,
    idempotency_key: str | None,
) -> dict[str, Any]:
    def apply(cursor, user_id: int) -> dict[str, Any]:
        cursor.execute(
            f"""INSERT INTO {_table('analysis_reports')}(user_id,title,thesis,tickers,report_text,source_context)
            VALUES(%s,%s,%s,%s,%s,%s) RETURNING id,created_at""",
            (user_id, title, thesis, tickers, report_text, Json(source_context)),
        )
        row = cursor.fetchone()
        return {
            "status": "success",
            "contract_version": "1.0",
            "report_id": row["id"],
            "tickers": tickers,
            "created_at": row["created_at"],
        }

    return _execute(
        user_email,
        "save_analysis_report",
        idempotency_key,
        confirmed,
        apply,
        _fingerprint(
            {
                "title": title,
                "thesis": thesis,
                "tickers": tickers,
                "report_text": report_text,
                "source_context": source_context,
            }
        ),
    )
