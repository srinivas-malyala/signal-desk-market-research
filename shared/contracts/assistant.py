"""Strict, non-executing assistant proposal candidates; ownership is server supplied."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from shared.contracts.models import Ticker

Tag = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]


class ProposalArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True, hide_input_in_errors=True)


class TickerArguments(ProposalArguments):
    ticker: str

    @field_validator("ticker")
    @classmethod
    def ticker_symbol(cls, value: str) -> str:
        return Ticker(symbol=value).symbol


class WatchlistArguments(TickerArguments):
    watchlist_name: Literal["Primary"] = "Primary"


class NoteArguments(TickerArguments):
    title: str = Field(min_length=1, max_length=200)
    note_text: str = Field(min_length=1, max_length=20_000)
    thesis_tags: list[Tag] = Field(default_factory=list, max_length=20)

class ReportArguments(ProposalArguments):
    title: str = Field(min_length=1, max_length=200)
    thesis: str = Field(default="", max_length=4_000)
    tickers: list[str] = Field(min_length=1, max_length=10)
    report_text: str = Field(min_length=1, max_length=100_000)

    @field_validator("tickers")
    @classmethod
    def ticker_symbols(cls, values: list[str]) -> list[str]:
        normalized = [Ticker(symbol=value).symbol for value in values]
        if len(set(normalized)) != len(normalized):
            raise ValueError("Report tickers must be distinct")
        return normalized


class WatchlistProposal(ProposalArguments):
    schema_version: Literal["1"] = "1"
    type: Literal["watchlist_add", "watchlist_remove"]
    arguments: WatchlistArguments


class NoteProposal(ProposalArguments):
    schema_version: Literal["1"] = "1"
    type: Literal["save_note"] = "save_note"
    arguments: NoteArguments


class ReportProposal(ProposalArguments):
    schema_version: Literal["1"] = "1"
    type: Literal["save_report"] = "save_report"
    arguments: ReportArguments


Proposal = Annotated[WatchlistProposal | NoteProposal | ReportProposal, Field(discriminator="type")]
