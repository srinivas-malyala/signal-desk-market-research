"""Business adapter: Massive calls, normalization, persistence and research logic."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, date, datetime, timedelta
from typing import Any

import action_service as actions
import lakebase
import requests
from lakehouse_market import fetch_market_bars
from massive_client import MassiveClient
from psycopg2.extras import Json

TICKER = re.compile(r"^[A-Z][A-Z0-9.-]{0,9}$")
_client: MassiveClient | None = None


def _table(base: str) -> str:
    return lakebase.table_name(base)


def client() -> MassiveClient:
    global _client
    if _client is None:
        _client = MassiveClient()
    return _client


def _symbol(value: str) -> str:
    symbol = (value or "").strip().upper()
    if not TICKER.fullmatch(symbol):
        raise ValueError("Ticker must be a valid 1-10 character U.S. market symbol.")
    return symbol


def _error(error: Exception) -> dict:
    if isinstance(error, ValueError):
        return {"status": "error", "error_code": "invalid_request", "message": str(error)}
    if isinstance(error, requests.HTTPError):
        status = error.response.status_code if error.response is not None else None
        message = "Massive could not return market data for that request."
        if status in (401, 403):
            message = "Massive denied this endpoint. Check the API secret and subscription entitlement."
        elif status == 404:
            message = "No Massive market data was found for that ticker."
        elif status == 429:
            message = "The Massive API rate limit was reached. Try again shortly."
        return {"status": "error", "error_code": f"massive_http_{status or 'error'}", "message": message}
    return {
        "status": "error",
        "error_code": "research_error",
        "message": "The research request could not be completed.",
    }


def _upsert_company(ticker: str, data: dict) -> None:
    address = data.get("address") or {}
    lakebase.write(
        f"""
      INSERT INTO {_table("companies")}(ticker,name,description,sector,industry,sic_code,primary_exchange,market_cap,
        weighted_shares_outstanding,currency,homepage_url,list_date,payload,synced_at)
      VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now())
      ON CONFLICT(ticker) DO UPDATE SET name=excluded.name,description=excluded.description,
        sector=excluded.sector,industry=excluded.industry,sic_code=excluded.sic_code,
        primary_exchange=excluded.primary_exchange,market_cap=excluded.market_cap,
        weighted_shares_outstanding=excluded.weighted_shares_outstanding,currency=excluded.currency,
        homepage_url=excluded.homepage_url,list_date=excluded.list_date,payload=excluded.payload,synced_at=now()
    """,
        (
            ticker,
            data.get("name"),
            data.get("description"),
            None,
            data.get("sic_description"),
            data.get("sic_code"),
            data.get("primary_exchange"),
            data.get("market_cap"),
            data.get("weighted_shares_outstanding"),
            data.get("currency_name"),
            data.get("homepage_url"),
            data.get("list_date"),
            Json({**data, "normalized_address": address}),
        ),
    )


def _bar(row: dict) -> dict:
    ts = datetime.fromtimestamp(row["t"] / 1000, tz=UTC)
    return {
        "date": ts.date().isoformat(),
        "captured_at": ts.isoformat(),
        "open": row.get("o"),
        "high": row.get("h"),
        "low": row.get("l"),
        "close": row.get("c"),
        "vwap": row.get("vw"),
        "volume": row.get("v"),
        "transactions": row.get("n"),
    }


def _save_bars(ticker: str, raw: list[dict]) -> None:
    for index, row in enumerate(raw):
        current = _bar(row)
        previous = raw[index - 1].get("c") if index else None
        change = (row.get("c") - previous) if previous and row.get("c") is not None else None
        pct = (change / previous * 100) if previous and change is not None else None
        lakebase.write(
            f"""
          INSERT INTO {_table("price_snapshots")}(ticker,captured_at,open,high,low,close,vwap,volume,previous_close,change_amount,change_percent,payload)
          VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
          ON CONFLICT(ticker,captured_at) DO UPDATE SET open=excluded.open,high=excluded.high,low=excluded.low,
            close=excluded.close,vwap=excluded.vwap,volume=excluded.volume,previous_close=excluded.previous_close,
            change_amount=excluded.change_amount,change_percent=excluded.change_percent,payload=excluded.payload
        """,
            (
                ticker,
                current["captured_at"],
                current["open"],
                current["high"],
                current["low"],
                current["close"],
                current["vwap"],
                current["volume"],
                previous,
                change,
                pct,
                Json(row),
            ),
        )


def _news_record(ticker: str, item: dict) -> dict:
    insights = [i for i in item.get("insights", []) if i.get("ticker") == ticker]
    insight = insights[0] if insights else {}
    linked_tickers = sorted({ticker, *(str(value.get("ticker")) for value in item.get("insights", []) if value.get("ticker"))})
    publisher = item.get("publisher") or {}
    return {
        "id": item.get("id") or hashlib.sha256(f"{ticker}:{item.get('article_url')}".encode()).hexdigest(),
        "ticker": ticker,
        "tickers": linked_tickers,
        "title": item.get("title"),
        "description": item.get("description"),
        "author": item.get("author"),
        "article_url": item.get("article_url"),
        "publisher": publisher.get("name") if isinstance(publisher, dict) else str(publisher),
        "keywords": item.get("keywords") or [],
        "sentiment": insight.get("sentiment"),
        "sentiment_reasoning": insight.get("sentiment_reasoning"),
        "published_at": item.get("published_utc"),
    }


def _save_news(records: list[dict], raw_by_id: dict[str, dict]) -> None:
    for row in records:
        raw = raw_by_id[row["id"]]
        lakebase.write(
            f"""
          INSERT INTO {_table("news_articles")}(id,ticker,title,description,author,article_url,publisher,keywords,sentiment,
            sentiment_reasoning,published_at,payload,synced_at)
          VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now())
          ON CONFLICT(id) DO UPDATE SET title=excluded.title,description=excluded.description,author=excluded.author,
            article_url=excluded.article_url,publisher=excluded.publisher,keywords=excluded.keywords,
            sentiment=excluded.sentiment,sentiment_reasoning=excluded.sentiment_reasoning,
            published_at=excluded.published_at,payload=excluded.payload,synced_at=now()
        """,
            (
                row["id"],
                row["ticker"],
                row["title"] or "Untitled",
                row["description"],
                row["author"],
                row["article_url"],
                row["publisher"],
                Json(row["keywords"]),
                row["sentiment"],
                row["sentiment_reasoning"],
                row["published_at"],
                Json(raw),
            ),
        )
        insight_by_ticker = {value.get("ticker"): value for value in raw.get("insights", []) if value.get("ticker")}
        for ticker in row["tickers"]:
            insight = insight_by_ticker.get(ticker) or {}
            lakebase.write(
                f"""INSERT INTO {_table('news_article_tickers')}
                (article_id,ticker,sentiment,sentiment_reasoning) VALUES(%s,%s,%s,%s)
                ON CONFLICT(article_id,ticker) DO UPDATE SET sentiment=excluded.sentiment,
                sentiment_reasoning=excluded.sentiment_reasoning""",
                (row["id"], ticker, insight.get("sentiment"), insight.get("sentiment_reasoning")),
            )


def get_stock_performance(ticker: str, lookback_days: int = 30, access_token: str | None = None) -> dict:
    try:
        symbol = _symbol(ticker)
        days = min(max(int(lookback_days), 2), 365)
        end = date.today()
        requested_start = end - timedelta(days=days)
        fetch_start = requested_start - timedelta(days=8)
        history_source = "Unity Catalog silver_market_bars joined to gold_stock_performance"
        history_fallback: str | None = None
        try:
            bars = fetch_market_bars(
                symbol,
                requested_start.isoformat(),
                end.isoformat(),
                access_token=access_token,
            )
        except Exception as history_error:
            history_fallback = "Governed warehouse history was unavailable; Massive daily aggregates were used."
            raw = sorted(
                client().get_daily_bars(symbol, fetch_start.isoformat(), end.isoformat()),
                key=lambda row: row["t"],
            )
            if not raw:
                raise ValueError(f"No daily price bars were found for {symbol}.") from history_error
            _save_bars(symbol, raw)
            bars = [bar for bar in (_bar(row) for row in raw) if bar["date"] >= requested_start.isoformat()]
            history_source = "Massive Stocks API daily aggregates"
        if not bars:
            raise ValueError(f"No daily price bars were found in the requested window for {symbol}.")
        first, last = bars[0], bars[-1]
        change = (
            last["close"] - first["close"]
            if last["close"] is not None and first["close"] is not None
            else None
        )
        change_percent = change / first["close"] * 100 if change is not None and first["close"] else None
        try:
            snapshot = client().get_snapshot(symbol)
            current = {
                "available": True,
                "price": (snapshot.get("lastTrade") or {}).get("p") or (snapshot.get("day") or {}).get("c"),
                "today_change": snapshot.get("todaysChange"),
                "today_change_percent": snapshot.get("todaysChangePerc"),
                "day": snapshot.get("day"),
                "previous_day": snapshot.get("prevDay"),
                "updated": snapshot.get("updated"),
            }
        except requests.HTTPError as exc:
            current = {"available": False, "message": _error(exc)["message"], "fallback": "latest daily aggregate"}
        return {
            "status": "success",
            "ticker": symbol,
            "lookback_days": days,
            "requested_period": {"start": requested_start.isoformat(), "end": end.isoformat()},
            "actual_period": {"start": first["date"], "end": last["date"]},
            "as_of": last["date"],
            "fetched_at": datetime.now(UTC).isoformat(),
            "current_snapshot": current,
            "latest": last,
            "period_start_close": first["close"],
            "change_amount": round(change, 4) if change is not None else None,
            "change_percent": round(change_percent, 2) if change_percent is not None else None,
            "period_high": max((x["high"] for x in bars if x["high"] is not None), default=None),
            "period_low": min((x["low"] for x in bars if x["low"] is not None), default=None),
            "daily_bars": bars,
            "source": history_source,
            "limitations": [
                "The requested period uses calendar days; the actual period contains available trading sessions only.",
                *([history_fallback] if history_fallback else []),
            ],
        }
    except Exception as error:
        return _error(error)


def get_company_research(ticker: str, news_limit: int = 10, include_fundamentals: bool = True) -> dict:
    try:
        symbol = _symbol(ticker)
        details = client().get_ticker_details(symbol)
        if not details:
            raise ValueError(f"No company profile was found for {symbol}.")
        _upsert_company(symbol, details)
        raw_news = client().get_news(symbol, min(max(int(news_limit), 1), 50))
        news = [_news_record(symbol, item) for item in raw_news]
        _save_news(news, {record["id"]: raw for record, raw in zip(news, raw_news, strict=True)})
        try:
            filings = client().get_filings(symbol, 10)
        except requests.HTTPError as exc:
            filings = {"available": False, "message": _error(exc)["message"], "items": []}
        fundamentals: dict[str, Any] = {"available": False, "message": "Fundamentals were not requested."}
        if include_fundamentals:
            try:
                fundamentals = {
                    "available": True,
                    "income_statements": client().get_income_statements(symbol),
                    "balance_sheets": client().get_balance_sheets(symbol),
                }
            except requests.HTTPError as exc:
                fundamentals = {"available": False, "message": _error(exc)["message"]}
        profile = {
            key: details.get(key)
            for key in (
                "ticker",
                "name",
                "description",
                "sic_code",
                "sic_description",
                "primary_exchange",
                "market_cap",
                "weighted_shares_outstanding",
                "currency_name",
                "homepage_url",
                "list_date",
            )
        }
        return {
            "status": "success",
            "ticker": symbol,
            "profile": profile,
            "fundamentals": fundamentals,
            "filings": filings,
            "news": news,
            "source": "Massive Stocks API",
            "fetched_at": datetime.now(UTC).isoformat(),
            "limitations": [
                "Fundamental endpoint availability depends on the configured Massive subscription entitlement.",
                "Use SEC Company Facts for authoritative exact reported values.",
            ],
        }
    except Exception as error:
        return _error(error)


def compare_stocks(tickers: list[str], lookback_days: int = 30, access_token: str | None = None) -> dict:
    if not isinstance(tickers, list) or not 2 <= len(tickers) <= 5:
        return _error(ValueError("Provide between 2 and 5 tickers to compare."))
    try:
        symbols = [_symbol(ticker) for ticker in tickers]
    except Exception as error:
        return _error(error)
    if len(set(symbols)) != len(symbols):
        return _error(ValueError("Provide between 2 and 5 distinct tickers to compare."))
    comparisons, errors = [], []
    for ticker in symbols:
        result = get_stock_performance(ticker, lookback_days, access_token)
        if result.get("status") == "success":
            comparisons.append(
                {k: result[k] for k in ("ticker", "as_of", "latest", "change_percent", "period_high", "period_low")}
            )
        else:
            errors.append({"ticker": ticker, "message": result.get("message")})
    if not comparisons:
        return {
            "status": "error",
            "error_code": "no_comparisons",
            "message": "No ticker could be compared.",
            "errors": errors,
        }
    return {"status": "success", "lookback_days": lookback_days, "comparisons": comparisons, "errors": errors}


def _email(email: str) -> str:
    normalized = (email or "").strip().lower()
    if "@" not in normalized or len(normalized) > 320:
        raise ValueError("A valid user email is required.")
    return normalized


def get_watchlist(user_email: str, watchlist_name: str = "Primary") -> dict:
    try:
        email = _email(user_email)
        name = (watchlist_name or "Primary").strip()
        rows = lakebase.query(
            f"""SELECT wt.ticker,wt.added_at,c.name,c.description,c.market_cap,
          p.close,p.change_percent,p.captured_at FROM {_table("watchlist_tickers")} wt
          JOIN {_table("watchlists")} w ON w.id=wt.watchlist_id
          JOIN {_table("users")} u ON u.id=w.user_id
          LEFT JOIN {_table("companies")} c ON c.ticker=wt.ticker
          LEFT JOIN LATERAL (SELECT close,change_percent,captured_at FROM {_table("price_snapshots")} WHERE ticker=wt.ticker ORDER BY captured_at DESC LIMIT 1) p ON true
          WHERE u.email=%s AND w.name=%s ORDER BY wt.added_at""",
            (email, name),
        )
        return {"status": "success", "watchlist": name, "tickers": rows}
    except Exception as error:
        return _error(error)


def update_watchlist(
    user_email: str,
    ticker: str,
    action: str,
    watchlist_name: str = "Primary",
    *,
    confirmed: bool = False,
    idempotency_key: str | None = None,
) -> dict:
    try:
        symbol = _symbol(ticker)
        verb = (action or "").lower()
        if verb not in ("add", "remove"):
            raise ValueError("action must be 'add' or 'remove'.")
        name = (watchlist_name or "Primary").strip()
        if not name or len(name) > 100:
            raise ValueError("watchlist_name must contain 1-100 characters.")
        return actions.update_watchlist(
            user_email,
            symbol,
            verb,
            name,
            confirmed=confirmed,
            idempotency_key=idempotency_key,
        )
    except Exception as error:
        return _error(error)


def save_research_note(
    user_email: str,
    ticker: str,
    title: str,
    note_text: str,
    thesis_tags: list[str] | None = None,
    *,
    confirmed: bool = False,
    idempotency_key: str | None = None,
) -> dict:
    try:
        symbol = _symbol(ticker)
        clean_title = title.strip()
        clean_note = note_text.strip()
        tags = [str(tag).strip() for tag in (thesis_tags or []) if str(tag).strip()]
        if not clean_title or not clean_note:
            raise ValueError("title and note_text are required.")
        if len(clean_title) > 200 or len(clean_note) > 20_000:
            raise ValueError("Note title or body exceeds the allowed size.")
        if len(tags) > 20 or any(len(tag) > 64 for tag in tags):
            raise ValueError("thesis_tags must contain at most 20 labels of 64 characters.")
        return actions.save_research_note(
            user_email,
            symbol,
            clean_title,
            clean_note,
            tags,
            confirmed=confirmed,
            idempotency_key=idempotency_key,
        )
    except Exception as error:
        return _error(error)


def save_analysis_report(
    user_email: str,
    title: str,
    thesis: str,
    tickers: list[str],
    report_text: str,
    source_context: dict | None = None,
    *,
    confirmed: bool = False,
    idempotency_key: str | None = None,
) -> dict:
    try:
        symbols = [_symbol(t) for t in tickers]
        clean_title = title.strip()
        clean_report = report_text.strip()
        context = source_context or {}
        if not clean_title or not clean_report:
            raise ValueError("title and report_text are required.")
        if len(clean_title) > 200 or len(clean_report) > 100_000:
            raise ValueError("Report title or body exceeds the allowed size.")
        if len(json.dumps(context, default=str)) > 32_000:
            raise ValueError("source_context exceeds the allowed size.")
        return actions.save_analysis_report(
            user_email,
            clean_title,
            thesis.strip(),
            symbols,
            clean_report,
            context,
            confirmed=confirmed,
            idempotency_key=idempotency_key,
        )
    except Exception as error:
        return _error(error)


def semantic_research(
    query: str,
    top_k: int = 5,
    tickers: list[str] | None = None,
    source_types: list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    access_token: str | None = None,
) -> dict:
    try:
        from research_search import ResearchSearch

        symbols = [_symbol(ticker) for ticker in tickers] if tickers else None
        return ResearchSearch(access_token=access_token).search(
            query,
            top_k=top_k,
            tickers=symbols,
            source_types=source_types,
            start_date=start_date,
            end_date=end_date,
        )
    except Exception as error:
        return _error(error)


def get_notable_updates(user_email: str, move_threshold_percent: float = 5.0, mark_visited: bool = False) -> dict:
    try:
        email = _email(user_email)
        rows = lakebase.query(f"SELECT id,last_visit_at FROM {_table('users')} WHERE email=%s", (email,))
        if not rows:
            return {
                "status": "success",
                "since": datetime.now(UTC) - timedelta(days=7),
                "notable_price_moves": [],
                "new_articles": [],
                "price_move_threshold_percent": abs(float(move_threshold_percent)),
            }
        user_id = rows[0]["id"]
        since = rows[0]["last_visit_at"] or datetime.now(UTC) - timedelta(days=7)
        moves = lakebase.query(
            f"""SELECT DISTINCT ON(p.ticker) p.ticker,p.close,p.change_percent,p.captured_at
          FROM {_table("price_snapshots")} p JOIN {_table("watchlist_tickers")} wt ON wt.ticker=p.ticker
          JOIN {_table("watchlists")} w ON w.id=wt.watchlist_id
          WHERE w.user_id=%s AND p.captured_at>%s AND abs(coalesce(p.change_percent,0)) >= %s
          ORDER BY p.ticker,p.captured_at DESC""",
            (user_id, since, abs(float(move_threshold_percent))),
        )
        news = lakebase.query(
            f"""SELECT nat.ticker,n.title,nat.sentiment,n.published_at,n.article_url
          FROM {_table("news_articles")} n
          JOIN {_table("news_article_tickers")} nat ON nat.article_id=n.id
          JOIN {_table("watchlist_tickers")} wt ON wt.ticker=nat.ticker
          JOIN {_table("watchlists")} w ON w.id=wt.watchlist_id
          WHERE w.user_id=%s AND n.published_at>%s ORDER BY n.published_at DESC LIMIT 50""",
            (user_id, since),
        )
        if mark_visited:
            lakebase.write(
                f"UPDATE {_table('users')} SET last_visit_at=now(),updated_at=now() WHERE id=%s",
                (user_id,),
            )
        return {
            "status": "success",
            "since": since,
            "notable_price_moves": moves,
            "new_articles": news,
            "price_move_threshold_percent": abs(float(move_threshold_percent)),
        }
    except Exception as error:
        return _error(error)
