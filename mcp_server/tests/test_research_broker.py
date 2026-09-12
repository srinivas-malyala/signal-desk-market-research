from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import research_broker as broker


def test_invalid_ticker_returns_clean_error():
    result = broker.get_stock_performance("not a ticker!", 30)
    assert result["status"] == "error"
    assert result["error_code"] == "invalid_request"

def test_performance_calculates_return(monkeypatch):
    fake = Mock()
    first = datetime.now(UTC) - timedelta(days=2)
    last = datetime.now(UTC) - timedelta(days=1)
    fake.get_daily_bars.return_value = [
        {"t": int(first.timestamp() * 1000), "o": 99, "h": 101, "l": 98, "c": 100, "v": 10},
        {"t": int(last.timestamp() * 1000), "o": 100, "h": 111, "l": 99, "c": 110, "v": 20},
    ]
    fake.get_snapshot.return_value = {"lastTrade": {"p": 110}, "todaysChangePerc": 1.2}
    monkeypatch.setattr(broker, "client", lambda: fake)
    monkeypatch.setattr(broker, "_save_bars", lambda *args: None)
    result = broker.get_stock_performance("aapl", 30)
    assert result["status"] == "success"
    assert result["ticker"] == "AAPL"
    assert result["change_percent"] == 10.0
    assert result["requested_period"]["start"] <= result["actual_period"]["start"]

def test_compare_requires_two_tickers():
    result = broker.compare_stocks(["AAPL"], 30)
    assert result["status"] == "error"


def test_company_mapping_does_not_invent_sector(monkeypatch):
    writes = []
    monkeypatch.setattr(broker.lakebase, "write", lambda _sql, params, *_args: writes.append(params))
    broker._upsert_company("AAPL", {"name": "Apple", "sic_description": "Electronic Computers"})
    assert writes[0][3] is None
    assert writes[0][4] == "Electronic Computers"


def test_performance_prefers_governed_lakehouse_history(monkeypatch):
    fake = Mock()
    fake.get_snapshot.return_value = {"lastTrade": {"p": 110}}
    monkeypatch.setattr(broker, "client", lambda: fake)
    monkeypatch.setattr(
        broker,
        "fetch_market_bars",
        lambda *_args, **_kwargs: [
            {"date": "2026-09-01", "open": 99.0, "high": 101.0, "low": 98.0, "close": 100.0, "volume": 10.0},
            {"date": "2026-09-10", "open": 100.0, "high": 111.0, "low": 99.0, "close": 110.0, "volume": 20.0},
        ],
    )
    result = broker.get_stock_performance("AAPL", 30)
    assert result["status"] == "success"
    assert result["source"].startswith("Unity Catalog")
    fake.get_daily_bars.assert_not_called()
