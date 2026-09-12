"""Pure reference transformations for synthetic Lakebase CDC acceptance tests."""

from __future__ import annotations

import hashlib
import math
from collections import defaultdict
from datetime import datetime
from typing import Any

CHANGE_TYPES = frozenset({"insert", "update_preimage", "update_postimage", "delete"})
EFFECTIVE_CHANGE_TYPES = frozenset({"insert", "update_postimage", "delete"})
SOURCE_CONTRACTS = {
    "agent_tool_events": ("event_id",),
    "agent_sessions": ("session_id",),
    "watchlist_tickers": ("watchlist_id", "ticker"),
    "research_notes": ("id",),
    "analysis_reports": ("id",),
}


def _timestamp(value: Any) -> datetime:
    text = str(value or "").strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include an offset")
    return parsed


def _pseudonym(user_id: Any) -> str | None:
    if user_id is None:
        return None
    value = f"signal-desk-lakebase-user:{user_id}".encode()
    return hashlib.sha256(value).hexdigest()


def _record_key(source_table: str, row: dict[str, Any]) -> str:
    values = [str(row.get(field) or "").strip() for field in SOURCE_CONTRACTS[source_table]]
    if any(not value for value in values):
        raise ValueError("source primary key is incomplete")
    return ":".join(values)


def _event_timestamp(source_table: str, change_type: str, row: dict[str, Any], synced_at: datetime) -> datetime:
    if change_type == "delete":
        return synced_at
    if source_table == "agent_sessions":
        field = "created_at" if change_type == "insert" else "last_activity_at"
        return _timestamp(row[field]) if row.get(field) else synced_at
    candidates = {
        "agent_tool_events": ("created_at",),
        "watchlist_tickers": ("last_viewed_at", "added_at"),
        "research_notes": ("updated_at", "created_at"),
        "analysis_reports": ("created_at",),
    }[source_table]
    for name in candidates:
        if row.get(name):
            return _timestamp(row[name])
    return synced_at


def _action_type(source_table: str, change_type: str, row: dict[str, Any]) -> str:
    if change_type == "update_preimage":
        return "update_preimage"
    if change_type == "delete":
        return "delete"
    if change_type == "update_postimage":
        return "update"
    if source_table == "agent_tool_events":
        value = str(row.get("action_type") or "").strip()
        if value not in {"retrieve", "create", "update", "delete"}:
            raise ValueError("agent action_type is invalid")
        return value
    return "create"


def normalize_change_events(events: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Normalize safe analytics fields and quarantine malformed envelopes."""
    accepted: list[dict[str, Any]] = []
    quarantined: list[dict[str, Any]] = []
    for position, envelope in enumerate(events):
        source_table = str(envelope.get("source_table") or "")
        try:
            if source_table not in SOURCE_CONTRACTS:
                raise ValueError("source table is not allowlisted")
            change_type = str(envelope.get("_pg_change_type") or "")
            if change_type not in CHANGE_TYPES:
                raise ValueError("change type is invalid")
            if envelope.get("_pg_lsn") is None or envelope.get("_sort_by") is None:
                raise ValueError("ordering metadata is missing")
            pg_lsn = int(envelope["_pg_lsn"])
            sort_by = int(envelope["_sort_by"])
            if pg_lsn < 0 or sort_by < 0:
                raise ValueError("ordering metadata must be nonnegative")
            synced_at = _timestamp(envelope["_timestamp"])
            row = envelope.get("row")
            if not isinstance(row, dict):
                raise ValueError("row payload must be an object")
            record_key = _record_key(source_table, row)
            change_material = f"{source_table}||{record_key}||{change_type}||{pg_lsn}".encode()
            event_timestamp = _event_timestamp(source_table, change_type, row, synced_at)
            duration = row.get("duration_ms")
            duration_ms = int(duration) if duration is not None else None
            if duration_ms is not None and duration_ms < 0:
                raise ValueError("duration must be nonnegative")
            accepted.append(
                {
                    "change_id": hashlib.sha256(change_material).hexdigest(),
                    "source_table": source_table,
                    "record_key": record_key,
                    "change_type": change_type,
                    "pg_lsn": pg_lsn,
                    "pg_xid": int(envelope["_pg_xid"]) if envelope.get("_pg_xid") is not None else None,
                    "sort_by": sort_by,
                    "synced_at": synced_at.isoformat(),
                    "event_timestamp": event_timestamp.isoformat(),
                    "user_pseudonym": _pseudonym(row.get("user_id")),
                    "session_id": str(row.get("session_id")) if row.get("session_id") else None,
                    "tool_name": str(row.get("tool_name")) if row.get("tool_name") else {
                        "watchlist_tickers": "update_watchlist",
                        "research_notes": "save_research_note",
                        "analysis_reports": "save_analysis_report",
                    }.get(source_table),
                    "status": str(row.get("status")) if row.get("status") else (
                        None if source_table == "agent_sessions" else "success"
                    ),
                    "duration_ms": duration_ms,
                    "action_type": _action_type(source_table, change_type, row),
                    "source_latency_seconds": int((synced_at - event_timestamp).total_seconds()),
                }
            )
        except (KeyError, TypeError, ValueError) as exc:
            quarantined.append(
                {
                    "position": position,
                    "source_table": source_table or None,
                    "reason": str(exc),
                }
            )
    return accepted, quarantined


def silver_agent_activity(changes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove preimages and idempotently retain one copy of each operation."""
    deduplicated: dict[str, dict[str, Any]] = {}
    for change in changes:
        if change["change_type"] not in EFFECTIVE_CHANGE_TYPES:
            continue
        prior = deduplicated.get(change["change_id"])
        ordering = (change["sort_by"], change["synced_at"])
        if prior is None or ordering > (prior["sort_by"], prior["synced_at"]):
            deduplicated[change["change_id"]] = {**change, "activity_date": change["event_timestamp"][:10]}
    return sorted(deduplicated.values(), key=lambda row: (row["event_timestamp"], row["change_id"]))


def _nearest_rank(values: list[int], percentile: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(percentile * len(ordered)) - 1)]


def _freshness(rows: list[dict[str, Any]], source: str, refreshed_at: str) -> dict[str, Any]:
    return {
        "source_max_synced_at": max(row["synced_at"] for row in rows),
        "metric_refreshed_at": refreshed_at,
        "metric_source": source,
    }


def build_gold_metrics(activity: list[dict[str, Any]], *, refreshed_at: str) -> dict[str, list[dict[str, Any]]]:
    """Calculate the five Phase 6.2 metric families from safe Silver rows."""
    agent = [
        row
        for row in activity
        if row["source_table"] == "agent_tool_events" and row["change_type"] == "insert"
    ]

    daily_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    tool_groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    watchlist_groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    save_groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in agent:
        daily_groups[row["activity_date"]].append(row)
        tool_groups[(row["activity_date"], row["tool_name"])].append(row)
    for row in activity:
        if row["source_table"] == "watchlist_tickers":
            watchlist_groups[(row["activity_date"], row["action_type"])].append(row)
        if row["source_table"] in {"research_notes", "analysis_reports"}:
            research_type = "note" if row["source_table"] == "research_notes" else "report"
            save_groups[(row["activity_date"], research_type, row["action_type"])].append(row)

    daily_active = []
    error_rates = []
    for activity_date, rows in sorted(daily_groups.items()):
        freshness = _freshness(rows, "silver_agent_activity:agent_tool_events", refreshed_at)
        daily_active.append(
            {
                "activity_date": activity_date,
                "daily_active_researchers": len({row["user_pseudonym"] for row in rows if row["user_pseudonym"]}),
                "agent_invocations": len(rows),
                "max_source_latency_seconds": max(row["source_latency_seconds"] for row in rows),
                **freshness,
            }
        )
        errors = sum(row["status"] == "error" for row in rows)
        error_rates.append(
            {
                "activity_date": activity_date,
                "invocation_count": len(rows),
                "error_count": errors,
                "error_rate": round(errors / len(rows), 4),
                **freshness,
            }
        )

    tool_usage = []
    for (activity_date, tool_name), rows in sorted(tool_groups.items()):
        durations = [row["duration_ms"] for row in rows if row["duration_ms"] is not None]
        tool_usage.append(
            {
                "activity_date": activity_date,
                "tool_name": tool_name,
                "invocation_count": len(rows),
                "success_count": sum(row["status"] == "success" for row in rows),
                "error_count": sum(row["status"] == "error" for row in rows),
                "null_duration_count": len(rows) - len(durations),
                "average_duration_ms": round(sum(durations) / len(durations), 2) if durations else None,
                "p50_duration_ms": _nearest_rank(durations, 0.5),
                "p95_duration_ms": _nearest_rank(durations, 0.95),
                **_freshness(rows, "silver_agent_activity:agent_tool_events", refreshed_at),
            }
        )

    watchlist = [
        {
            "activity_date": key[0],
            "action_type": key[1],
            "change_count": len(rows),
            "max_source_latency_seconds": max(row["source_latency_seconds"] for row in rows),
            **_freshness(rows, "silver_agent_activity:watchlist_tickers", refreshed_at),
        }
        for key, rows in sorted(watchlist_groups.items())
    ]
    research_saves = [
        {
            "activity_date": key[0],
            "research_type": key[1],
            "action_type": key[2],
            "change_count": len(rows),
            "researcher_count": len({row["user_pseudonym"] for row in rows if row["user_pseudonym"]}),
            "max_source_latency_seconds": max(row["source_latency_seconds"] for row in rows),
            **_freshness(rows, "silver_agent_activity:research_notes,analysis_reports", refreshed_at),
        }
        for key, rows in sorted(save_groups.items())
    ]
    return {
        "daily_active_researchers": daily_active,
        "tool_usage_latency": tool_usage,
        "agent_error_rate": error_rates,
        "watchlist_changes": watchlist,
        "research_saves": research_saves,
    }
