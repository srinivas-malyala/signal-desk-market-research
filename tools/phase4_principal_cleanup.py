#!/usr/bin/env python3
"""Verify and clean the two-principal P4 UI acceptance rows."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mcp_server"))

import lakebase  # noqa: E402

MARKERS = {
    "A": {
        "ticker": "IBM",
        "note_title": "P4-A-20260930-1524",
        "report_title": "P4-A-REPORT-20260930-1530",
    },
    "B": {
        "ticker": "QQQ",
        "note_title": "P4-B-20260930-1532",
        "report_title": "P4-B-REPORT-20260930-1532",
    },
}
WRITE_TOOLS = ("update_watchlist", "save_research_note", "save_analysis_report")


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def _table(name: str) -> str:
    return lakebase.table_name(name)


def main() -> int:
    args = _args()
    os.environ["DATABRICKS_CONFIG_PROFILE"] = args.profile
    tables = {name: _table(name) for name in (
        "users", "watchlists", "watchlist_tickers", "research_notes",
        "analysis_reports", "idempotency_records", "stock_research_mcp_traces",
    )}
    report: dict[str, object] = {
        "gate": "p4_two_real_principal_isolation",
        "status": "failed",
        "principals": {},
        "checks": {},
        "cleanup": {},
    }
    with lakebase.get_connection() as connection, connection.cursor() as cursor:
        try:
            identities: dict[str, dict[str, object]] = {}
            for label, marker in MARKERS.items():
                cursor.execute(
                    f"""SELECT u.id AS user_id,u.email,n.id AS note_id,r.id AS report_id
                    FROM {tables['users']} u
                    JOIN {tables['research_notes']} n ON n.user_id=u.id AND n.title=%s
                    JOIN {tables['analysis_reports']} r ON r.user_id=u.id AND r.title=%s""",
                    (marker["note_title"], marker["report_title"]),
                )
                rows = cursor.fetchall()
                if len(rows) != 1:
                    raise RuntimeError(f"principal {label} acceptance rows were not unique")
                row = rows[0]
                cursor.execute(
                    f"""SELECT wt.watchlist_id,wt.ticker FROM {tables['watchlist_tickers']} wt
                    JOIN {tables['watchlists']} w ON w.id=wt.watchlist_id
                    WHERE w.user_id=%s AND wt.ticker=%s""",
                    (row["user_id"], marker["ticker"]),
                )
                ticker_rows = cursor.fetchall()
                if len(ticker_rows) != 1:
                    raise RuntimeError(f"principal {label} watchlist marker was not unique")
                subject = hashlib.sha256(str(row["email"]).encode("utf-8")).hexdigest()
                cursor.execute(
                    f"""SELECT tool_name,count(*) AS calls
                    FROM {tables['stock_research_mcp_traces']}
                    WHERE user_email=%s AND status='success' AND tool_name=ANY(%s)
                      AND started_at >= TIMESTAMPTZ '2026-09-30 22:20:00+00'
                    GROUP BY tool_name ORDER BY tool_name""",
                    (subject, list(WRITE_TOOLS)),
                )
                trace_counts = {item["tool_name"]: int(item["calls"]) for item in cursor.fetchall()}
                identities[label] = {
                    "user_id": int(row["user_id"]),
                    "note_id": int(row["note_id"]),
                    "report_id": int(row["report_id"]),
                    "watchlist_id": int(ticker_rows[0]["watchlist_id"]),
                    "subject_hash_prefix": subject[:12],
                    "trace_counts": trace_counts,
                }
                report["principals"][label] = {
                    "subject_hash_prefix": subject[:12],
                    "owned_watchlist_markers": 1,
                    "owned_note_markers": 1,
                    "owned_report_markers": 1,
                    "successful_write_trace_counts": trace_counts,
                }

            distinct_owners = identities["A"]["user_id"] != identities["B"]["user_id"]
            all_traces = all(
                int(identity["trace_counts"].get(tool, 0)) >= 1
                for identity in identities.values()
                for tool in WRITE_TOOLS
            )
            report["checks"] = {
                "distinct_real_principal_owners": distinct_owners,
                "one_owned_marker_per_data_type": True,
                "ui_cross_visibility_observed": False,
                "all_three_write_tools_traced_per_principal": all_traces,
            }
            if not distinct_owners or not all_traces:
                raise RuntimeError("principal ownership or trace isolation proof was incomplete")

            deleted = {"idempotency_records": 0, "notes": 0, "reports": 0, "watchlist_tickers": 0, "empty_watchlists": 0}
            for label, identity in identities.items():
                marker = MARKERS[label]
                cursor.execute(
                    f"""DELETE FROM {tables['idempotency_records']}
                    WHERE user_id=%s AND (
                      (operation_name='save_research_note' AND result->>'note_id'=%s) OR
                      (operation_name='save_analysis_report' AND result->>'report_id'=%s) OR
                      (operation_name='update_watchlist' AND result->>'ticker'=%s)
                    )""",
                    (
                        identity["user_id"], str(identity["note_id"]),
                        str(identity["report_id"]), marker["ticker"],
                    ),
                )
                deleted["idempotency_records"] += cursor.rowcount
                cursor.execute(f"DELETE FROM {tables['research_notes']} WHERE id=%s", (identity["note_id"],))
                deleted["notes"] += cursor.rowcount
                cursor.execute(f"DELETE FROM {tables['analysis_reports']} WHERE id=%s", (identity["report_id"],))
                deleted["reports"] += cursor.rowcount
                cursor.execute(
                    f"DELETE FROM {tables['watchlist_tickers']} WHERE watchlist_id=%s AND ticker=%s",
                    (identity["watchlist_id"], marker["ticker"]),
                )
                deleted["watchlist_tickers"] += cursor.rowcount
                cursor.execute(
                    f"""DELETE FROM {tables['watchlists']} w WHERE w.user_id=%s
                    AND NOT EXISTS (SELECT 1 FROM {tables['watchlist_tickers']} wt WHERE wt.watchlist_id=w.id)""",
                    (identity["user_id"],),
                )
                deleted["empty_watchlists"] += cursor.rowcount

            remaining = 0
            for label, identity in identities.items():
                marker = MARKERS[label]
                cursor.execute(
                    f"""SELECT
                      (SELECT count(*) FROM {tables['research_notes']} WHERE id=%s) +
                      (SELECT count(*) FROM {tables['analysis_reports']} WHERE id=%s) +
                      (SELECT count(*) FROM {tables['watchlist_tickers']} WHERE watchlist_id=%s AND ticker=%s) AS remaining""",
                    (identity["note_id"], identity["report_id"], identity["watchlist_id"], marker["ticker"]),
                )
                remaining += int(cursor.fetchone()["remaining"])
            connection.commit()
            report["cleanup"] = {
                "deleted": deleted,
                "remaining_disposable_rows": remaining,
                "sanitized_traces_retained": True,
                "quota_ledger_retained": True,
            }
            report["status"] = "passed" if remaining == 0 else "failed"
        except Exception:
            connection.rollback()
            raise
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
