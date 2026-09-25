"""FastMCP stock-market research server for Databricks Agent Bricks."""

from __future__ import annotations

import inspect
import json
import logging
import os
import re
import time
import uuid
from contextvars import ContextVar
from datetime import UTC, datetime
from functools import wraps

import lakebase
import research_broker as broker
from audit import bounded_value, pseudonymous_subject, result_summary, safe_parameters, trusted_email
from fastmcp import FastMCP
from psycopg2.extras import Json
from starlette.middleware import Middleware as ASGIMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

mcp = FastMCP("stock-market-research")
_identity: ContextVar[dict | None] = ContextVar("identity", default=None)
_session: ContextVar[str] = ContextVar("session", default="")
_correlation: ContextVar[str] = ContextVar("correlation", default="")
logger = logging.getLogger("signal_desk.mcp")
CORRELATION_ID = re.compile(r"^[A-Za-z0-9._:-]{1,100}$")
ACTION_TYPES = {
    "update_watchlist": "update",
    "save_research_note": "create",
    "save_analysis_report": "create",
    "get_notable_updates": "retrieve",
}


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        requested_correlation = request.headers.get("x-request-id", "")
        correlation_id = (
            requested_correlation if CORRELATION_ID.fullmatch(requested_correlation) else str(uuid.uuid4())
        )
        identity = _identity.set(
            {
                "email": request.headers.get("x-forwarded-email") or request.headers.get("x-forwarded-user"),
                "access_token": request.headers.get("x-forwarded-access-token"),
            }
        )
        session = _session.set(str(uuid.uuid4()))
        correlation = _correlation.set(correlation_id)
        try:
            response = await call_next(request)
            response.headers["x-request-id"] = correlation_id
            return response
        finally:
            _identity.reset(identity)
            _session.reset(session)
            _correlation.reset(correlation)


@mcp.custom_route("/health", methods=["GET"])
async def health_check(_request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "stock-market-research", "contract_version": "1.0"})


def _trusted_email() -> str:
    return trusted_email(_identity.get())


def _write_audit(tool_name: str, started: datetime, duration_ms: int, parameters: dict, result: dict) -> None:
    session_id = _session.get() or str(uuid.uuid4())
    email = (_identity.get() or {}).get("email")
    status = "error" if result.get("status") == "error" else "success"
    summary = result_summary(result)
    with lakebase.get_connection() as connection, connection.cursor() as cursor:
        cursor.execute(
            f"""INSERT INTO {lakebase.table_name('stock_research_mcp_traces')}
            (session_id,server_name,tool_name,tool_parameters,user_email,started_at,duration_ms,status,result,error_message)
            VALUES(%s,'stock-market-research',%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                session_id,
                tool_name,
                Json(parameters),
                pseudonymous_subject(email),
                started,
                duration_ms,
                status,
                Json(summary),
                bounded_value(result.get("message")) if status == "error" else None,
            ),
        )
        if email and "@" in str(email):
            cursor.execute(
                f"""INSERT INTO {lakebase.table_name('users')}(email) VALUES(%s)
                ON CONFLICT(email) DO UPDATE SET updated_at=now() RETURNING id""",
                (str(email).strip().lower(),),
            )
            user_id = cursor.fetchone()["id"]
            cursor.execute(
                f"""INSERT INTO {lakebase.table_name('agent_sessions')}(session_id,user_id,last_activity_at)
                VALUES(%s,%s,now()) ON CONFLICT(session_id) DO UPDATE SET last_activity_at=now()""",
                (session_id, user_id),
            )
            cursor.execute(
                f"""INSERT INTO {lakebase.table_name('agent_tool_events')}
                (session_id,user_id,tool_name,action_type,status,duration_ms,metadata)
                VALUES(%s,%s,%s,%s,%s,%s,%s)""",
                (
                    session_id,
                    user_id,
                    tool_name,
                    ACTION_TYPES.get(tool_name, "retrieve"),
                    status,
                    duration_ms,
                    Json({"parameters": parameters, "result": summary}),
                ),
            )
        connection.commit()


def traced(function):
    """Persist bounded tool metadata; tracing failures never fail the tool."""

    @wraps(function)
    def wrapper(*args, **kwargs):
        started = datetime.now(UTC)
        timer = time.perf_counter()
        bound = inspect.signature(function).bind(*args, **kwargs)
        bound.apply_defaults()
        try:
            result = function(*args, **kwargs)
        except Exception as error:
            result = broker._error(error)
        result.setdefault("contract_version", "1.0")
        result.setdefault("correlation_id", _correlation.get() or str(uuid.uuid4()))
        duration_ms = int((time.perf_counter() - timer) * 1000)
        try:
            _write_audit(
                function.__name__,
                started,
                duration_ms,
                safe_parameters(dict(bound.arguments)),
                result,
            )
        except Exception:
            pass
        logger.info(
            json.dumps(
                {
                    "event": "mcp_tool_completed",
                    "tool": function.__name__,
                    "status": result.get("status", "success"),
                    "error_code": result.get("error_code"),
                    "duration_ms": duration_ms,
                    "correlation_id": result["correlation_id"],
                },
                sort_keys=True,
            )
        )
        return result

    return wrapper


@mcp.tool
@traced
def get_stock_performance(ticker: str, lookback_days: int = 30) -> dict:
    """Get real historical daily bars and summarize a ticker's recent performance.

    Args:
        ticker: U.S. equity ticker, such as AAPL.
        lookback_days: Calendar-day lookback from 2 through 365.
    Returns:
        Latest OHLCV, period return/high/low and underlying daily bars.
    """
    return broker.get_stock_performance(ticker, lookback_days, (_identity.get() or {}).get("access_token"))


@mcp.tool
@traced
def get_company_research(ticker: str, news_limit: int = 10, include_fundamentals: bool = True) -> dict:
    """Get a company profile, recent news and available reported fundamentals.

    Args:
        ticker: U.S. equity ticker.
        news_limit: Number of recent articles, 1-50.
        include_fundamentals: Request income statements and balance sheets.
    Returns:
        Normalized company, SEC filing links, news and fundamentals data with
        clear entitlement errors.
    """
    return broker.get_company_research(ticker, news_limit, include_fundamentals)


@mcp.tool
@traced
def compare_stocks(tickers: list[str], lookback_days: int = 30) -> dict:
    """Compare recent price action for two to five tickers on the same window.

    Args:
        tickers: Two to five U.S. equity tickers.
        lookback_days: Shared calendar-day comparison window.
    Returns:
        Like-for-like latest price, return, period high and low per ticker.
    """
    return broker.compare_stocks(tickers, lookback_days, (_identity.get() or {}).get("access_token"))


@mcp.tool
@traced
def get_watchlist(watchlist_name: str = "Primary") -> dict:
    """Read a user's watchlist with the latest locally synced price facts.

    Args:
        watchlist_name: Named list, default Primary.
    Returns:
        Current membership and latest available stored company/price facts.
    """
    return broker.get_watchlist(_trusted_email(), watchlist_name)


@mcp.tool
@traced
def update_watchlist(
    ticker: str,
    action: str,
    watchlist_name: str = "Primary",
    confirmed: bool = False,
    idempotency_key: str | None = None,
) -> dict:
    """Add or remove one ticker from a named user watchlist.

    Args:
        ticker: U.S. equity ticker.
        action: Exactly ``add`` or ``remove``.
        watchlist_name: Watchlist name; defaults to Primary.
        confirmed: Must be true after explicit user confirmation.
        idempotency_key: Stable 8-128 character retry key for this requested action.
    """
    return broker.update_watchlist(
        _trusted_email(),
        ticker,
        action,
        watchlist_name,
        confirmed=confirmed,
        idempotency_key=idempotency_key,
    )


@mcp.tool
@traced
def save_research_note(
    ticker: str,
    title: str,
    note_text: str,
    thesis_tags: list[str] | None = None,
    confirmed: bool = False,
    idempotency_key: str | None = None,
) -> dict:
    """Persist a user's explicit research note tied to one ticker.

    Args:
        ticker: U.S. equity ticker.
        title: Short note title.
        note_text: User-confirmed research note.
        thesis_tags: Optional thematic labels.
        confirmed: Must be true after explicit user confirmation.
        idempotency_key: Stable 8-128 character retry key for this requested action.
    Returns:
        New note ID and creation time.
    """
    return broker.save_research_note(
        _trusted_email(),
        ticker,
        title,
        note_text,
        thesis_tags,
        confirmed=confirmed,
        idempotency_key=idempotency_key,
    )


@mcp.tool
@traced
def save_analysis_report(
    title: str,
    thesis: str,
    tickers: list[str],
    report_text: str,
    source_context: dict | None = None,
    confirmed: bool = False,
    idempotency_key: str | None = None,
) -> dict:
    """Persist an analysis report only after the user asks to save it.

    Args:
        title: Report title.
        thesis: Investing question or hypothesis.
        tickers: Tickers covered by the report.
        report_text: User-confirmed report body.
        source_context: Optional provenance metadata from earlier tool calls.
        confirmed: Must be true after explicit user confirmation.
        idempotency_key: Stable 8-128 character retry key for this requested action.
    Returns:
        New report ID and creation time.
    """
    return broker.save_analysis_report(
        _trusted_email(),
        title,
        thesis,
        tickers,
        report_text,
        source_context,
        confirmed=confirmed,
        idempotency_key=idempotency_key,
    )


@mcp.tool
@traced
def semantic_research(
    query: str,
    top_k: int = 5,
    tickers: list[str] | None = None,
    source_types: list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    """Retrieve attributable SEC filing and news passages from managed AI Search.

    Args:
        query: Natural-language investing thesis or research question.
        top_k: Number of parent-deduplicated passages, 1-5.
        tickers: Optional ticker filter.
        source_types: Optional ``filing`` or ``article`` filter.
        start_date: Optional inclusive source date in YYYY-MM-DD format.
        end_date: Optional inclusive source date in YYYY-MM-DD format.
    """
    identity = _identity.get() or {}
    return broker.semantic_research(
        query,
        top_k,
        tickers,
        source_types,
        start_date,
        end_date,
        identity.get("access_token"),
    )


@mcp.tool
@traced
def get_notable_updates(move_threshold_percent: float = 5.0, mark_visited: bool = False) -> dict:
    """Return notable watchlist price moves and new articles since last visit.

    Args:
        move_threshold_percent: Absolute daily percentage threshold.
        mark_visited: Advance last-visit time after successful retrieval.
    Returns:
        Locally synced qualifying moves, articles, and the comparison timestamp.
    """
    return broker.get_notable_updates(_trusted_email(), move_threshold_percent, mark_visited)


if __name__ == "__main__":
    lakebase.migrate()
    try:
        port = int(os.environ.get("PORT", "8000"))
    except ValueError as error:
        raise RuntimeError("PORT must be an integer.") from error
    if not 1 <= port <= 65_535:
        raise RuntimeError("PORT must be between 1 and 65535.")
    mcp.run(
        transport="http",
        host="0.0.0.0",
        port=port,
        middleware=[ASGIMiddleware(RequestContextMiddleware)],
    )
