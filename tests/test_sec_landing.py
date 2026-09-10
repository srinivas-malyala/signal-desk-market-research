from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from ingestion.sec_client import SecResponse
from ingestion.sec_landing import (
    CompanyTarget,
    FilingRecord,
    SecLandingIntegrityError,
    SecLandingStore,
    parse_recent_filings,
    run_sec_landing,
)

FIXTURES = Path(__file__).parents[1] / "fixtures" / "sec"


def sec_response(content: bytes, url: str, content_type: str = "application/json") -> SecResponse:
    return SecResponse(content, content_type, 200, 25, url)


class FakeSecClient:
    def __init__(self) -> None:
        self.http_attempts = 0
        self.retries = 0
        self.submissions = json.loads((FIXTURES / "submissions.json").read_text())

    def get_submissions(self, cik: str):
        self.http_attempts += 1
        content = json.dumps(self.submissions).encode()
        response = sec_response(content, f"https://data.sec.gov/submissions/CIK{cik}.json")
        return self.submissions, response

    def get_company_facts(self, cik: str):
        self.http_attempts += 1
        payload = json.loads((FIXTURES / "companyfacts.json").read_text())
        content = json.dumps(payload).encode()
        return payload, sec_response(content, f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json")

    def get_filing_document(self, cik: str, accession: str, primary_document: str):
        self.http_attempts += 1
        content = (FIXTURES / "filing.html").read_bytes()
        url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}/{primary_document}"
        return sec_response(content, url, "text/html")


def test_recent_filings_include_amendments_and_ignore_unselected_forms() -> None:
    payload = json.loads((FIXTURES / "submissions.json").read_text())
    filings = parse_recent_filings(payload, max_filings=10)
    assert [filing.form for filing in filings] == ["10-Q", "10-Q/A"]
    assert all(filing.accession_number.startswith("0000320193-") for filing in filings)


def test_snapshot_is_content_addressed_idempotent_and_cacheable(tmp_path: Path) -> None:
    fixed = datetime(2026, 9, 10, 12, tzinfo=UTC)
    store = SecLandingStore(tmp_path, clock=lambda: fixed)
    target = CompanyTarget("AAPL", "0000320193")
    first_response = sec_response(b'{"version":1}', "https://data.sec.gov/submissions/CIK0000320193.json")

    first, first_created = store.land_snapshot("submissions", target, first_response)
    second, second_created = store.land_snapshot("submissions", target, first_response)

    assert first_created is True
    assert second_created is False
    assert first["landing_path"] == second["landing_path"]
    assert store.cached_snapshot("submissions", target.cik, timedelta(hours=24)) == first

    changed, changed_created = store.land_snapshot(
        "submissions",
        target,
        sec_response(b'{"version":2}', first_response.source_url),
    )
    assert changed_created is True
    assert changed["checksum_sha256"] != first["checksum_sha256"]


def test_filing_accession_is_immutable(tmp_path: Path) -> None:
    store = SecLandingStore(tmp_path)
    target = CompanyTarget("AAPL", "0000320193")
    filing = FilingRecord(
        "0000320193-25-000079",
        "10-Q",
        "2025-08-01",
        "2025-06-28",
        "2025-08-01T16:31:12.000Z",
        "aapl.htm",
        "10-Q",
    )
    response = sec_response(b"<html>one</html>", "https://www.sec.gov/Archives/edgar/data/example")
    store.land_filing(target, filing, response)
    with pytest.raises(SecLandingIntegrityError, match="Immutable filing changed"):
        store.land_filing(
            target,
            filing,
            sec_response(b"<html>changed</html>", response.source_url),
        )


def test_two_company_landing_replays_without_network_calls(tmp_path: Path) -> None:
    targets = [CompanyTarget("AAPL", "0000320193"), CompanyTarget("MSFT", "0000789019")]
    store = SecLandingStore(tmp_path)
    first_client = FakeSecClient()
    first = run_sec_landing(targets, first_client, store, max_filings_per_company=1)
    assert first.submissions_landed == 2
    assert first.company_facts_landed == 2
    assert first.filing_documents_landed == 2
    assert first.failures == 0

    second_client = FakeSecClient()
    second = run_sec_landing(targets, second_client, store, max_filings_per_company=1)
    assert second.cached_requests == 4
    assert second.filing_documents_cached == 2
    assert second.http_attempts == 0
