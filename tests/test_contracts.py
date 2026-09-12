from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from shared.contracts import AgentEvent, ErrorEnvelope, MarketBar, ResearchChunk, Ticker

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


def test_research_chunk_contract_matches_phase5_parent_child_schema() -> None:
    digest = "a" * 64
    chunk = ResearchChunk(
        chunk_id=digest,
        parent_id="b" * 64,
        source_type="filing",
        source_id="0000320193-25-000079",
        tickers=["aapl"],
        ticker="aapl",
        chunk_index=0,
        section_name="Item 7. Management's Discussion",
        chunk_to_retrieve="Net sales increased.",
        chunk_to_embed="Ticker: AAPL\nNet sales increased.",
        chunk_token_count=3,
        parent_text="Net sales increased because services grew.",
        parent_token_count=6,
        chunk_content_hash=digest,
        source_content_hash="c" * 64,
        source_url="https://www.sec.gov/example",
    )
    assert chunk.tickers == ["AAPL"] and chunk.ticker == "AAPL"


def test_agent_event_uses_database_action_vocabulary() -> None:
    event = AgentEvent(
        event_id="1",
        session_id="session",
        tool_name="semantic_research",
        action_type="retrieve",
        status="success",
        started_at=datetime.now(UTC),
        duration_ms=5,
        correlation_id="correlation",
    )
    assert event.action_type == "retrieve"
