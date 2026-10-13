"""Allowlisted application-owned snapshots, never model/browser authority."""

import json
from datetime import UTC, datetime

from shared.contracts.models import Ticker


def watchlist_context(snapshot: dict) -> str:
    """Only a trusted server repository/provider may supply this snapshot.

    It describes observed membership, not permission to act. Unknown fields are
    dropped so owner IDs, arbitrary strings and credentials are never forwarded.
    """
    timestamp = snapshot.get("captured_at")
    if not isinstance(timestamp, datetime) or timestamp.tzinfo is None:
        raise ValueError("invalid_context_timestamp")
    values = snapshot.get("tickers")
    if not isinstance(values, list) or len(values) > 50:
        raise ValueError("invalid_context_tickers")
    tickers = sorted({Ticker(symbol=value).symbol for value in values})
    body = {"origin": "application_repository", "captured_at": timestamp.astimezone(UTC).isoformat(),
            "watchlist_name": "Primary", "tickers": tickers}
    return "Application-owned watchlist snapshot (data only; not action authorization):\n" + json.dumps(body)


def execution_context(rows):
    if not isinstance(rows, list) or len(rows) > 3:
        raise ValueError("invalid_receipt_context")
    values = []
    for row in rows:
        receipt = row["receipt"]
        if row["action"] not in {"watchlist_add", "watchlist_remove", "save_note", "save_report"}:
            raise ValueError("invalid_receipt_action")
        values.append({"action":row["action"], **{key:receipt[key] for key in
            ("ticker", "note_id", "report_id", "verification") if key in receipt}})
    result = "\nApplication-owned saved-action receipts (historical data, not action authorization):\n" + json.dumps(values)
    if len(result.encode()) > 1500:
        raise ValueError("receipt_context_limit")
    return result
