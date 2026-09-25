"""Pure helpers for trusted identity and bounded audit metadata."""

from __future__ import annotations

import hashlib

SENSITIVE_PARAMETERS = frozenset({"note_text", "report_text", "source_context", "thesis", "idempotency_key"})


def trusted_email(identity: dict | None) -> str:
    email = str((identity or {}).get("email") or "").strip().lower()
    if "@" not in email or len(email) > 320:
        raise ValueError("A trusted user identity is required.")
    return email


def pseudonymous_subject(email: str | None) -> str | None:
    if not email:
        return None
    return hashlib.sha256(str(email).strip().lower().encode("utf-8")).hexdigest()


def bounded_value(value):
    if isinstance(value, str):
        return value if len(value) <= 200 else f"{value[:200]}…"
    if isinstance(value, list):
        return [bounded_value(item) for item in value[:10]]
    if isinstance(value, dict):
        return {str(key)[:80]: bounded_value(item) for key, item in list(value.items())[:20]}
    if isinstance(value, (bool, int, float)) or value is None:
        return value
    return str(value)[:200]


def safe_parameters(arguments: dict) -> dict:
    safe = {}
    for name, value in arguments.items():
        if name in SENSITIVE_PARAMETERS:
            safe[name] = {
                "provided": value not in (None, "", {}, []),
                "characters": len(value) if isinstance(value, str) else None,
            }
        else:
            safe[name] = bounded_value(value)
    return safe


def result_summary(result: dict) -> dict:
    summary = {
        key: bounded_value(result[key])
        for key in (
            "status",
            "contract_version",
            "error_code",
            "ticker",
            "tickers",
            "action",
            "changed",
            "watchlist",
            "note_id",
            "report_id",
            "count",
            "as_of",
            "correlation_id",
        )
        if key in result
    }
    collection_counts = {
        key: len(result[key])
        for key in (
            "daily_bars",
            "news",
            "matches",
            "comparisons",
            "errors",
            "notable_price_moves",
            "new_articles",
        )
        if isinstance(result.get(key), list)
    }
    if collection_counts:
        summary["collection_counts"] = collection_counts
    return summary
