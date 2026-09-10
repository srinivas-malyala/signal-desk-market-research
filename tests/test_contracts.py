from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from shared.contracts import ErrorEnvelope, MarketBar, Ticker

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "contracts"


@pytest.mark.contract
def test_valid_market_bar_fixture_round_trips() -> None:
    payload = json.loads((FIXTURES / "market_bar.valid.json").read_text())
    bar = MarketBar.model_validate(payload)
    assert bar.ticker == "AAPL"
    assert bar.model_dump(mode="json")["trading_date"] == "2026-08-28"


@pytest.mark.contract
def test_invalid_market_bar_fixture_is_rejected() -> None:
    payload = json.loads((FIXTURES / "market_bar.invalid.json").read_text())
    with pytest.raises(ValidationError):
        MarketBar.model_validate(payload)


def test_ticker_contract_matches_existing_normalization() -> None:
    assert Ticker(symbol=" brk.b ").symbol == "BRK.B"
    with pytest.raises(ValidationError):
        Ticker(symbol="not a ticker")


def test_error_contract_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        ErrorEnvelope(error_code="invalid", message="bad input", secret="must not pass")
