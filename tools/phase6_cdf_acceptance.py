#!/usr/bin/env python3
"""Create and clean up a bounded five-table Lakebase CDC acceptance sequence."""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mcp_server import lakebase


def run_sequence() -> dict[str, object]:
    marker = uuid.uuid4().hex
    session_id = uuid.uuid4()
    tables = {base: lakebase.table_name(base) for base in (
        "users",
        "watchlists",
        "watchlist_tickers",
        "research_notes",
        "analysis_reports",
        "agent_sessions",
        "agent_tool_events",
    )}
    committed_at = datetime.now(UTC)

    with lakebase.get_connection() as connection, connection.cursor() as cursor:
        try:
            cursor.execute(
                f"INSERT INTO {tables['users']}(email,display_name) VALUES(%s,%s) RETURNING id",
                (f"phase6-cdf-{marker}@example.invalid", "Phase 6 CDC acceptance"),
            )
            user_id = int(cursor.fetchone()["id"])

            cursor.execute(
                f"INSERT INTO {tables['watchlists']}(user_id,name,is_default) "
                "VALUES(%s,%s,true) RETURNING id",
                (user_id, f"phase6-{marker}"),
            )
            watchlist_id = int(cursor.fetchone()["id"])
            cursor.execute(
                f"INSERT INTO {tables['watchlist_tickers']}(watchlist_id,ticker) VALUES(%s,%s)",
                (watchlist_id, "PH6X"),
            )
            cursor.execute(
                f"UPDATE {tables['watchlist_tickers']} SET last_viewed_at=now() "
                "WHERE watchlist_id=%s AND ticker=%s",
                (watchlist_id, "PH6X"),
            )

            cursor.execute(
                f"INSERT INTO {tables['research_notes']}(user_id,ticker,title,note_text) "
                "VALUES(%s,%s,%s,%s) RETURNING id",
                (user_id, "PH6X", f"phase6-{marker}", "bounded CDC acceptance note"),
            )
            note_id = int(cursor.fetchone()["id"])
            cursor.execute(
                f"UPDATE {tables['research_notes']} SET note_text=%s,updated_at=now() WHERE id=%s",
                ("updated bounded CDC acceptance note", note_id),
            )

            cursor.execute(
                f"INSERT INTO {tables['analysis_reports']}"
                "(user_id,title,thesis,tickers,report_text,source_context) "
                "VALUES(%s,%s,%s,%s,%s,%s::jsonb) RETURNING id",
                (
                    user_id,
                    f"phase6-{marker}",
                    "bounded CDC acceptance",
                    ["PH6X"],
                    "bounded CDC acceptance report",
                    json.dumps({"acceptance_marker": marker}),
                ),
            )
            report_id = int(cursor.fetchone()["id"])

            cursor.execute(
                f"INSERT INTO {tables['agent_sessions']}(session_id,user_id,status) VALUES(%s,%s,%s)",
                (str(session_id), user_id, "active"),
            )
            cursor.execute(
                f"UPDATE {tables['agent_sessions']} SET status=%s,last_activity_at=now() WHERE session_id=%s",
                ("completed", str(session_id)),
            )

            cursor.execute(
                f"INSERT INTO {tables['agent_tool_events']}"
                "(session_id,user_id,tool_name,action_type,status,duration_ms,metadata) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb) RETURNING event_id",
                (
                    str(session_id),
                    user_id,
                    "phase6_cdf_acceptance",
                    "retrieve",
                    "success",
                    123,
                    json.dumps({"acceptance_marker": marker}),
                ),
            )
            event_id = int(cursor.fetchone()["event_id"])
            cursor.execute(
                f"UPDATE {tables['agent_tool_events']} SET status=%s,duration_ms=%s WHERE event_id=%s",
                ("error", 456, event_id),
            )
            cursor.execute(f"DELETE FROM {tables['agent_tool_events']} WHERE event_id=%s", (event_id,))
            cursor.execute(f"DELETE FROM {tables['users']} WHERE id=%s", (user_id,))
            if cursor.rowcount != 1:
                raise RuntimeError("acceptance user cleanup did not delete exactly one row")
            connection.commit()
            committed_at = datetime.now(UTC)
        except Exception:
            connection.rollback()
            raise

    remaining = lakebase.query(
        f"""SELECT
          (SELECT count(*) FROM {tables['users']} WHERE id=%s) AS users,
          (SELECT count(*) FROM {tables['watchlists']} WHERE id=%s) AS watchlists,
          (SELECT count(*) FROM {tables['watchlist_tickers']} WHERE watchlist_id=%s) AS watchlist_tickers,
          (SELECT count(*) FROM {tables['research_notes']} WHERE id=%s) AS research_notes,
          (SELECT count(*) FROM {tables['analysis_reports']} WHERE id=%s) AS analysis_reports,
          (SELECT count(*) FROM {tables['agent_sessions']} WHERE session_id=%s) AS agent_sessions,
          (SELECT count(*) FROM {tables['agent_tool_events']} WHERE event_id=%s) AS agent_tool_events""",
        (user_id, watchlist_id, watchlist_id, note_id, report_id, str(session_id), event_id),
    )[0]
    cleanup_complete = all(int(value) == 0 for value in remaining.values())
    if not cleanup_complete:
        raise RuntimeError("controlled CDC acceptance cleanup is incomplete")

    return {
        "marker": marker,
        "committed_at": committed_at.isoformat(),
        "keys": {
            "watchlist_id": watchlist_id,
            "watchlist_ticker": "PH6X",
            "research_note_id": note_id,
            "analysis_report_id": report_id,
            "agent_session_id": str(session_id),
            "agent_tool_event_id": event_id,
        },
        "expected_history_rows": {
            "watchlist_tickers": 4,
            "research_notes": 4,
            "analysis_reports": 2,
            "agent_sessions": 4,
            "agent_tool_events": 4,
        },
        "cleanup_complete": cleanup_complete,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True, help="Explicit Databricks CLI/SDK profile")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    os.environ["DATABRICKS_CONFIG_PROFILE"] = args.profile
    print(json.dumps(run_sequence(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
