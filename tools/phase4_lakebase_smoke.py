"""Sanitized Lakebase connectivity, migration, and disposable CRUD verification."""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mcp_server import lakebase


def preflight() -> dict:
    rows = lakebase.query(
        """SELECT
          current_setting('server_version_num')::int >= 170000 AS postgres_17_or_newer,
          has_schema_privilege(current_user, %s, 'USAGE') AS operational_schema_usage,
          has_schema_privilege(current_user, %s, 'CREATE') AS operational_schema_create,
          has_schema_privilege(current_user, %s, 'USAGE') AS graph_schema_usage,
          EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'vector') AS vector_installed""",
        (lakebase.get_schema_name(), lakebase.get_schema_name(), lakebase.get_graph_schema_name()),
    )
    if len(rows) != 1:
        raise RuntimeError("Lakebase preflight returned an unexpected result")
    result = dict(rows[0])
    result["connected"] = True
    result["operational_schema"] = lakebase.get_schema_name()
    result["graph_schema"] = lakebase.get_graph_schema_name()
    result["table_suffix"] = lakebase.get_table_suffix()
    return result


def migrated_table_count() -> int:
    rows = lakebase.query(
        """SELECT count(*) AS table_count FROM information_schema.tables
           WHERE table_schema = %s AND table_name = ANY(%s)""",
        (
            lakebase.get_schema_name(),
            [f"{base}_{lakebase.get_table_suffix()}" for base in sorted(lakebase.TABLE_BASES)],
        ),
    )
    return int(rows[0]["table_count"])


def managed_table_ownership() -> dict:
    expected = [f"{base}_{lakebase.get_table_suffix()}" for base in sorted(lakebase.TABLE_BASES)]
    rows = lakebase.query(
        """SELECT count(*) AS observed_tables,
                  count(*) FILTER (WHERE tableowner = current_user) AS owned_by_current_role
           FROM pg_tables WHERE schemaname = %s AND tablename = ANY(%s)""",
        (lakebase.get_schema_name(), expected),
    )
    return {
        "expected_tables": len(expected),
        "observed_tables": int(rows[0]["observed_tables"]),
        "owned_by_current_role": int(rows[0]["owned_by_current_role"]),
    }


def cdc_replica_identity() -> dict:
    bases = ("watchlist_tickers", "research_notes", "analysis_reports", "agent_sessions", "agent_tool_events")
    expected = [f"{base}_{lakebase.get_table_suffix()}" for base in bases]
    rows = lakebase.query(
        """SELECT c.relname AS table_name, c.relreplident = 'f' AS replica_identity_full
           FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
           WHERE c.relkind = 'r' AND n.nspname = %s AND c.relname = ANY(%s)
           ORDER BY c.relname""",
        (lakebase.get_schema_name(), expected),
    )
    return {
        "expected_tables": len(expected),
        "observed_tables": len(rows),
        "full_replica_identity_tables": sum(bool(row["replica_identity_full"]) for row in rows),
        "all_ready": len(rows) == len(expected) and all(row["replica_identity_full"] for row in rows),
    }


def run_disposable_crud() -> dict:
    marker = uuid.uuid4().hex
    users = lakebase.table_name("users")
    notes = lakebase.table_name("research_notes")
    emails = (f"phase4-owner-{marker}@example.invalid", f"phase4-other-{marker}@example.invalid")
    with lakebase.get_connection() as connection, connection.cursor() as cursor:
        try:
            cursor.execute(
                f"INSERT INTO {users}(email) VALUES(%s),(%s) RETURNING id,email",
                emails,
            )
            created = {row["email"]: row["id"] for row in cursor.fetchall()}
            owner_id = created[emails[0]]
            other_id = created[emails[1]]
            cursor.execute(
                f"INSERT INTO {notes}(user_id,ticker,title,note_text) "
                "VALUES(%s,%s,%s,%s) RETURNING id",
                (owner_id, "AAPL", f"phase4-{marker}", "disposable phase4 verification"),
            )
            note_id = cursor.fetchone()["id"]
            cursor.execute(
                f"UPDATE {notes} SET note_text=%s,updated_at=now() WHERE id=%s AND user_id=%s",
                ("updated disposable phase4 verification", note_id, owner_id),
            )
            owner_update_count = cursor.rowcount
            cursor.execute(
                f"UPDATE {notes} SET note_text=%s WHERE id=%s AND user_id=%s",
                ("must not be written", note_id, other_id),
            )
            wrong_owner_update_count = cursor.rowcount
            cursor.execute(f"SELECT note_text FROM {notes} WHERE id=%s AND user_id=%s", (note_id, owner_id))
            updated_value_matches = cursor.fetchone()["note_text"] == "updated disposable phase4 verification"
            cursor.execute(f"DELETE FROM {users} WHERE id = ANY(%s)", ([owner_id, other_id],))
            deleted_users = cursor.rowcount
            cursor.execute(f"SELECT count(*) AS remaining FROM {notes} WHERE id=%s", (note_id,))
            remaining_notes = int(cursor.fetchone()["remaining"])
            connection.commit()
        except Exception:
            connection.rollback()
            raise
    return {
        "created_users": len(created),
        "owner_update_count": owner_update_count,
        "wrong_owner_update_count": wrong_owner_update_count,
        "updated_value_matches": updated_value_matches,
        "deleted_users": deleted_users,
        "remaining_notes_after_cascade": remaining_notes,
        "cleanup_complete": deleted_users == 2 and remaining_notes == 0,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True, help="Explicit Databricks CLI/SDK profile")
    parser.add_argument("--apply-migrations", action="store_true")
    parser.add_argument("--run-crud", action="store_true")
    args = parser.parse_args()
    if args.run_crud and not args.apply_migrations:
        parser.error("--run-crud requires --apply-migrations")
    return args


def main() -> int:
    args = parse_args()
    os.environ["DATABRICKS_CONFIG_PROFILE"] = args.profile
    report = {"preflight": preflight()}
    if args.apply_migrations:
        first_apply = lakebase.migrate()
        second_apply = lakebase.migrate()
        report["migrations"] = {
            "first_apply": first_apply,
            "second_apply": second_apply,
            "idempotent": not second_apply,
            "managed_table_count": migrated_table_count(),
            "expected_table_count": len(lakebase.TABLE_BASES),
            "ownership": managed_table_ownership(),
        }
        report["cdc_prerequisites"] = cdc_replica_identity()
    if args.run_crud:
        report["crud"] = run_disposable_crud()
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
