from __future__ import annotations

import hashlib
import logging
import re
import uuid
from pathlib import Path
from typing import Any

import lakebase
from flask import Flask, Response, g, jsonify, render_template, request
from mcp_client import (
    FastMCPWatchlistClient,
    MCPConfigurationError,
    MCPToolError,
    MCPUnavailableError,
    WatchlistClient,
)
from werkzeug.exceptions import HTTPException

APP_ROOT = Path(__file__).resolve().parent
app = Flask(
    __name__,
    template_folder=str(APP_ROOT / "templates"),
    static_folder=str(APP_ROOT / "static"),
)
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024
logger = logging.getLogger("signal_desk.frontend")

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
TICKER_PATTERN = re.compile(r"^[A-Z][A-Z0-9.-]{0,9}$")
IDEMPOTENCY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")
SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
        "connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
    ),
    "Cross-Origin-Opener-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Referrer-Policy": "no-referrer",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
}


def _error(message: str, status_code: int, error_code: str) -> tuple[Response, int]:
    return (
        jsonify(
            {
                "status": "error",
                "error_code": error_code,
                "message": message,
                "request_id": getattr(g, "request_id", None),
            }
        ),
        status_code,
    )


def _trusted_identity() -> tuple[str, str]:
    email = str(request.headers.get("X-Forwarded-Email") or "").strip().lower()
    token = str(request.headers.get("X-Forwarded-Access-Token") or "").strip()
    if not EMAIL_PATTERN.fullmatch(email) or len(email) > 320:
        raise ValueError("missing identity")
    if len(token) < 8 or len(token) > 16_384 or any(character.isspace() for character in token):
        raise ValueError("missing access token")
    return email, token


@app.before_request
def establish_request_context():
    g.request_id = str(uuid.uuid4())
    if request.endpoint == "health":
        return None
    try:
        g.user_email, g.user_access_token = _trusted_identity()
    except ValueError:
        return _error("Authenticated Databricks user identity is required.", 401, "authentication_required")
    return None


@app.after_request
def harden_response(response: Response) -> Response:
    response.headers["X-Request-ID"] = getattr(g, "request_id", str(uuid.uuid4()))
    response.headers["Cache-Control"] = "no-store"
    for name, value in SECURITY_HEADERS.items():
        response.headers[name] = value
    return response


@app.errorhandler(MCPConfigurationError)
def mcp_not_configured(_error_value: MCPConfigurationError):
    return _error("The research service is not configured.", 503, "mcp_not_configured")


@app.errorhandler(MCPUnavailableError)
def mcp_unavailable(_error_value: MCPUnavailableError):
    return _error("The research service is temporarily unavailable.", 502, "mcp_unavailable")


@app.errorhandler(MCPToolError)
def mcp_rejected(error_value: MCPToolError):
    return _error(str(error_value), 409, "mcp_action_rejected")


@app.errorhandler(Exception)
def unexpected_error(error_value: Exception):
    if isinstance(error_value, HTTPException):
        status_code = error_value.code or 400
        if status_code == 404:
            return _error("The requested resource was not found.", 404, "not_found")
        if status_code == 413:
            return _error("The request body exceeds the allowed size.", 413, "payload_too_large")
        return _error("The request was rejected.", status_code, "http_error")
    logger.error(
        "frontend_request_failed request_id=%s",
        getattr(g, "request_id", "missing"),
        exc_info=(type(error_value), error_value, error_value.__traceback__),
    )
    return _error("The request could not be completed.", 500, "internal_error")


def _table(base: str) -> str:
    return lakebase.table_name(base)


def _user_email() -> str:
    return str(g.user_email)


def _user_subject() -> str:
    return hashlib.sha256(_user_email().encode("utf-8")).hexdigest()


def _user_id() -> int:
    row = lakebase.write(
        f"INSERT INTO {_table('users')}(email) VALUES(%s) "
        "ON CONFLICT(email) DO UPDATE SET updated_at=now() RETURNING id",
        (_user_email(),),
        True,
    )
    return int(row["id"])


def _watchlist_client() -> WatchlistClient:
    factory = app.config.get("MCP_CLIENT_FACTORY")
    if factory is not None:
        return factory()
    return FastMCPWatchlistClient.from_environment()


def _request_payload() -> dict[str, Any]:
    payload = request.get_json(silent=True)
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise ValueError("JSON body must be an object.")
    return payload


def _idempotency_key() -> str:
    value = str(request.headers.get("Idempotency-Key") or f"frontend-{uuid.uuid4().hex}").strip()
    if not IDEMPOTENCY_PATTERN.fullmatch(value):
        raise ValueError("Idempotency-Key must contain 8-128 safe characters.")
    return value


@app.get("/")
def index():
    return render_template("index.html", user_email=_user_email())


@app.get("/healthz")
def health():
    return {"status": "ok", "service": "signal-desk-frontend", "contract_version": "1.0"}


@app.get("/api/overview")
def overview():
    uid = _user_id()
    watch = lakebase.query(
        f"""SELECT wt.ticker,c.name,p.close,p.change_percent,p.captured_at FROM {_table("watchlists")} w
          JOIN {_table("watchlist_tickers")} wt ON wt.watchlist_id=w.id
          LEFT JOIN {_table("companies")} c ON c.ticker=wt.ticker
          LEFT JOIN LATERAL(
            SELECT close,change_percent,captured_at FROM {_table("price_snapshots")}
            WHERE ticker=wt.ticker ORDER BY captured_at DESC LIMIT 1
          ) p ON true
          WHERE w.user_id=%s ORDER BY wt.added_at""",
        (uid,),
    )
    news = lakebase.query(
        f"""SELECT n.ticker,n.title,n.sentiment,n.published_at,n.article_url
          FROM {_table("news_articles")} n
          JOIN {_table("watchlist_tickers")} wt ON wt.ticker=n.ticker
          JOIN {_table("watchlists")} w ON w.id=wt.watchlist_id
          WHERE w.user_id=%s ORDER BY n.published_at DESC LIMIT 12""",
        (uid,),
    )
    notes = lakebase.query(
        f"SELECT id,ticker,title,note_text,created_at FROM {_table('research_notes')} "
        "WHERE user_id=%s ORDER BY created_at DESC LIMIT 8",
        (uid,),
    )
    reports = lakebase.query(
        f"SELECT id,title,tickers,thesis,created_at FROM {_table('analysis_reports')} "
        "WHERE user_id=%s ORDER BY created_at DESC LIMIT 8",
        (uid,),
    )
    activity = lakebase.query(
        f"SELECT tool_name,status,started_at,duration_ms FROM {_table('stock_research_mcp_traces')} "
        "WHERE user_email=%s ORDER BY started_at DESC LIMIT 10",
        (_user_subject(),),
    )
    return jsonify(
        {
            "user": _user_email(),
            "watchlist": watch,
            "news": news,
            "notes": notes,
            "reports": reports,
            "activity": activity,
            "request_id": g.request_id,
        }
    )


@app.post("/api/watchlist")
def add_ticker():
    try:
        ticker = str(_request_payload().get("ticker") or "").strip().upper()
        idempotency_key = _idempotency_key()
    except ValueError as exc:
        return _error(str(exc), 400, "invalid_request")
    if not TICKER_PATTERN.fullmatch(ticker):
        return _error("Enter a valid U.S. ticker.", 400, "invalid_ticker")
    result = _watchlist_client().update_watchlist(
        ticker=ticker,
        action="add",
        access_token=g.user_access_token,
        request_id=g.request_id,
        idempotency_key=idempotency_key,
    )
    return jsonify({**result, "request_id": g.request_id}), 201


@app.delete("/api/watchlist/<ticker>")
def remove_ticker(ticker: str):
    symbol = ticker.strip().upper()
    if not TICKER_PATTERN.fullmatch(symbol):
        return _error("Enter a valid U.S. ticker.", 400, "invalid_ticker")
    try:
        idempotency_key = _idempotency_key()
    except ValueError as exc:
        return _error(str(exc), 400, "invalid_request")
    result = _watchlist_client().update_watchlist(
        ticker=symbol,
        action="remove",
        access_token=g.user_access_token,
        request_id=g.request_id,
        idempotency_key=idempotency_key,
    )
    return jsonify({**result, "request_id": g.request_id})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
