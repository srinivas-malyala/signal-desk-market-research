"""Canonical Phase 0 data contracts.

These models define boundaries; they do not replace the prototype's public
dictionary responses during Phase 0. Later phases can adopt them one boundary
at a time while characterization tests protect compatibility.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

CONTRACT_VERSION = "1.0"
TICKER_PATTERN = re.compile(r"^[A-Z][A-Z0-9.-]{0,9}$")


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Ticker(ContractModel):
    symbol: str

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        symbol = value.strip().upper()
        if not TICKER_PATTERN.fullmatch(symbol):
            raise ValueError("invalid U.S. market ticker")
        return symbol


class ErrorEnvelope(ContractModel):
    status: Literal["error"] = "error"
    error_code: str = Field(min_length=1, max_length=80)
    message: str = Field(min_length=1, max_length=500)
    correlation_id: str | None = Field(default=None, max_length=100)
    retryable: bool = False
    contract_version: str = CONTRACT_VERSION


class MarketBar(ContractModel):
    ticker: str
    trading_date: date
    open: float
    high: float
    low: float
    close: float
    volume: float = Field(ge=0)
    vwap: float | None = None
    transactions: int | None = Field(default=None, ge=0)
    source_request_id: str | None = None
    ingested_at: datetime

    @field_validator("ticker")
    @classmethod
    def validate_ticker(cls, value: str) -> str:
        return Ticker(symbol=value).symbol

    @model_validator(mode="after")
    def validate_ohlc(self) -> MarketBar:
        if self.high < max(self.open, self.close, self.low):
            raise ValueError("high must be greater than or equal to OHLC values")
        if self.low > min(self.open, self.close, self.high):
            raise ValueError("low must be less than or equal to OHLC values")
        return self


class Article(ContractModel):
    article_id: str = Field(min_length=1, max_length=256)
    title: str = Field(min_length=1, max_length=1000)
    tickers: list[str] = Field(default_factory=list)
    article_url: str | None = None
    publisher: str | None = None
    published_at: datetime | None = None
    description: str | None = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("tickers")
    @classmethod
    def validate_tickers(cls, values: list[str]) -> list[str]:
        return [Ticker(symbol=value).symbol for value in values]


class Filing(ContractModel):
    accession_number: str = Field(pattern=r"^\d{10}-\d{2}-\d{6}$")
    cik: str = Field(pattern=r"^\d{10}$")
    ticker: str | None = None
    form: str = Field(min_length=1, max_length=20)
    filed_date: date
    source_url: str
    content_type: str | None = None
    checksum_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")

    @field_validator("ticker")
    @classmethod
    def validate_optional_ticker(cls, value: str | None) -> str | None:
        return None if value is None else Ticker(symbol=value).symbol


class ResearchChunk(ContractModel):
    chunk_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    parent_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_type: Literal["filing", "article"]
    source_id: str = Field(min_length=1, max_length=256)
    tickers: list[str] = Field(min_length=1)
    ticker: str | None = None
    chunk_index: int = Field(ge=0)
    section_name: str | None = Field(default=None, max_length=500)
    chunk_to_retrieve: str = Field(min_length=1, max_length=20_000)
    chunk_to_embed: str = Field(min_length=1, max_length=25_000)
    chunk_token_count: int = Field(ge=1, le=650)
    parent_text: str = Field(min_length=1, max_length=60_000)
    parent_token_count: int = Field(ge=1, le=1600)
    chunk_content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_url: str | None = None

    @field_validator("ticker")
    @classmethod
    def validate_optional_ticker(cls, value: str | None) -> str | None:
        return None if value is None else Ticker(symbol=value).symbol

    @field_validator("tickers")
    @classmethod
    def validate_tickers(cls, values: list[str]) -> list[str]:
        return [Ticker(symbol=value).symbol for value in values]


class AgentEvent(ContractModel):
    event_id: str = Field(min_length=1, max_length=100)
    session_id: str = Field(min_length=1, max_length=100)
    user_subject: str | None = Field(default=None, max_length=256)
    tool_name: str = Field(min_length=1, max_length=100)
    action_type: Literal["retrieve", "create", "update", "delete"]
    status: Literal["success", "error"]
    started_at: datetime
    duration_ms: int = Field(ge=0)
    correlation_id: str = Field(min_length=1, max_length=100)
    error_code: str | None = Field(default=None, max_length=80)


class ResearchNote(ContractModel):
    note_id: int | None = Field(default=None, ge=1)
    ticker: str
    title: str = Field(min_length=1, max_length=200)
    note_text: str = Field(min_length=1, max_length=20_000)
    thesis_tags: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("ticker")
    @classmethod
    def validate_ticker(cls, value: str) -> str:
        return Ticker(symbol=value).symbol


class AnalysisReport(ContractModel):
    report_id: int | None = Field(default=None, ge=1)
    title: str = Field(min_length=1, max_length=300)
    thesis: str | None = Field(default=None, max_length=5000)
    tickers: list[str] = Field(min_length=1, max_length=20)
    report_text: str = Field(min_length=1, max_length=100_000)
    source_context: dict[str, Any] = Field(default_factory=dict)

    @field_validator("tickers")
    @classmethod
    def validate_tickers(cls, values: list[str]) -> list[str]:
        return [Ticker(symbol=value).symbol for value in values]
