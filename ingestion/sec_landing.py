"""Immutable, content-addressed SEC landing contracts and orchestration."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    runtime_file = globals().get("__file__") or globals().get("filename")
    if runtime_file:
        sys.path.insert(0, str(Path(runtime_file).resolve().parents[1]))

from ingestion.market_backfill import _canonical_json_bytes, atomic_write  # noqa: E402
from ingestion.sec_client import SecClient, SecResponse  # noqa: E402
from shared.contracts.models import Ticker  # noqa: E402

ACCESSION_PATTERN = re.compile(r"^\d{10}-\d{2}-\d{6}$")
CIK_PATTERN = re.compile(r"^\d{10}$")
SELECTED_FORMS = frozenset({"10-K", "10-Q", "8-K"})


class SecLandingIntegrityError(RuntimeError):
    """Raised when an immutable SEC landing pair is incomplete or changed."""


@dataclass(frozen=True)
class CompanyTarget:
    ticker: str
    cik: str

    def __post_init__(self) -> None:
        normalized = Ticker(symbol=self.ticker).symbol
        if normalized != self.ticker:
            object.__setattr__(self, "ticker", normalized)
        if not CIK_PATTERN.fullmatch(self.cik):
            raise ValueError("CIK must contain exactly 10 digits")


@dataclass(frozen=True)
class FilingRecord:
    accession_number: str
    form: str
    filing_date: str
    report_date: str | None
    acceptance_datetime: str | None
    primary_document: str
    primary_doc_description: str | None


@dataclass
class SecLandingMetrics:
    companies: int = 0
    http_attempts: int = 0
    retries: int = 0
    cached_requests: int = 0
    submissions_landed: int = 0
    company_facts_landed: int = 0
    filing_documents_landed: int = 0
    filing_documents_cached: int = 0
    failures: int = 0


def parse_recent_filings(payload: dict[str, Any], max_filings: int) -> list[FilingRecord]:
    recent = payload.get("filings", {}).get("recent", {})
    accessions = recent.get("accessionNumber", [])
    if not isinstance(accessions, list):
        return []
    records: list[FilingRecord] = []
    for index, accession in enumerate(accessions):
        form = _array_value(recent, "form", index)
        primary_document = _array_value(recent, "primaryDocument", index)
        filing_date = _array_value(recent, "filingDate", index)
        base_form = form.removesuffix("/A") if isinstance(form, str) else ""
        if base_form not in SELECTED_FORMS:
            continue
        if not isinstance(accession, str) or not ACCESSION_PATTERN.fullmatch(accession):
            continue
        if not all(isinstance(value, str) and value for value in (form, primary_document, filing_date)):
            continue
        if Path(primary_document).name != primary_document or ".." in primary_document:
            continue
        records.append(
            FilingRecord(
                accession_number=accession,
                form=form,
                filing_date=filing_date,
                report_date=_array_value(recent, "reportDate", index),
                acceptance_datetime=_array_value(recent, "acceptanceDateTime", index),
                primary_document=primary_document,
                primary_doc_description=_array_value(recent, "primaryDocDescription", index),
            )
        )
        if len(records) >= max_filings:
            break
    return records


def _array_value(data: dict[str, Any], key: str, index: int) -> Any:
    values = data.get(key, [])
    return values[index] if isinstance(values, list) and index < len(values) else None


class SecLandingStore:
    def __init__(self, raw_root: Path, clock=lambda: datetime.now(UTC)) -> None:
        self.root = raw_root / "sec"
        self.clock = clock

    def _validate_pair(self, data_path: Path, manifest_path: Path) -> dict[str, Any] | None:
        if not data_path.exists() and not manifest_path.exists():
            return None
        if not data_path.exists() or not manifest_path.exists():
            raise SecLandingIntegrityError(f"Incomplete SEC landing pair at {data_path.parent}")
        try:
            content = data_path.read_bytes()
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise SecLandingIntegrityError(f"Unreadable SEC landing pair at {data_path.parent}") from error
        if manifest.get("checksum_sha256") != hashlib.sha256(content).hexdigest():
            raise SecLandingIntegrityError(f"SEC checksum mismatch at {data_path.parent}")
        return manifest

    def cached_snapshot(self, kind: str, cik: str, max_age: timedelta) -> dict[str, Any] | None:
        cache_path = self.root / kind / f"cik={cik}" / "cache.json"
        if not cache_path.exists():
            return None
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
            checked_at = datetime.fromisoformat(cache["checked_at"])
            manifest_path = Path(cache["manifest_path"])
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            data_path = Path(manifest["landing_path"])
        except (KeyError, OSError, ValueError, json.JSONDecodeError) as error:
            raise SecLandingIntegrityError(f"Corrupt SEC cache pointer for {kind}/{cik}") from error
        if self.clock() - checked_at > max_age:
            return None
        return self._validate_pair(data_path, manifest_path)

    def land_snapshot(
        self,
        kind: str,
        target: CompanyTarget,
        response: SecResponse,
    ) -> tuple[dict[str, Any], bool]:
        checksum = hashlib.sha256(response.content).hexdigest()
        directory = self.root / kind / f"cik={target.cik}" / f"checksum={checksum}"
        data_path = directory / "response.json"
        manifest_path = directory / "manifest.json"
        existing = self._validate_pair(data_path, manifest_path)
        created = existing is None
        if existing is None:
            atomic_write(data_path, response.content)
            existing = self._manifest(kind, target, response, data_path, checksum)
            atomic_write(manifest_path, _canonical_json_bytes(existing))
        cache = {
            "version": 1,
            "checked_at": self.clock().isoformat(),
            "manifest_path": str(manifest_path),
        }
        atomic_write(directory.parent / "cache.json", _canonical_json_bytes(cache))
        return existing, created

    def filing_manifest(self, target: CompanyTarget, filing: FilingRecord) -> dict[str, Any] | None:
        directory = self._filing_directory(target.cik, filing.accession_number)
        return self._validate_pair(directory / "document.html", directory / "manifest.json")

    def land_filing(
        self,
        target: CompanyTarget,
        filing: FilingRecord,
        response: SecResponse,
    ) -> tuple[dict[str, Any], bool]:
        directory = self._filing_directory(target.cik, filing.accession_number)
        data_path = directory / "document.html"
        manifest_path = directory / "manifest.json"
        checksum = hashlib.sha256(response.content).hexdigest()
        existing = self._validate_pair(data_path, manifest_path)
        if existing is not None:
            if existing["checksum_sha256"] != checksum:
                raise SecLandingIntegrityError(f"Immutable filing changed: {filing.accession_number}")
            return existing, False
        atomic_write(data_path, response.content)
        manifest = self._manifest(
            "filing",
            target,
            response,
            data_path,
            checksum,
            filing=filing,
        )
        atomic_write(manifest_path, _canonical_json_bytes(manifest))
        return manifest, True

    def _filing_directory(self, cik: str, accession: str) -> Path:
        return self.root / "filings" / f"cik={cik}" / f"accession={accession}"

    def _manifest(
        self,
        kind: str,
        target: CompanyTarget,
        response: SecResponse,
        data_path: Path,
        checksum: str,
        *,
        filing: FilingRecord | None = None,
    ) -> dict[str, Any]:
        return {
            "version": 1,
            "source": "sec_edgar",
            "kind": kind,
            "ticker": target.ticker,
            "cik": target.cik,
            "accession_number": filing.accession_number if filing else None,
            "form": filing.form if filing else None,
            "filing_date": filing.filing_date if filing else None,
            "report_date": filing.report_date if filing else None,
            "acceptance_datetime": filing.acceptance_datetime if filing else None,
            "primary_document": filing.primary_document if filing else None,
            "primary_doc_description": filing.primary_doc_description if filing else None,
            "source_url": response.source_url,
            "content_type": response.content_type,
            "status_code": response.status_code,
            "byte_count": len(response.content),
            "checksum_sha256": checksum,
            "fetched_at": self.clock().isoformat(),
            "landing_path": str(data_path),
        }


def run_sec_landing(
    targets: list[CompanyTarget],
    client: SecClient,
    store: SecLandingStore,
    *,
    max_filings_per_company: int = 6,
    snapshot_ttl: timedelta = timedelta(hours=24),
    max_workers: int = 2,
) -> SecLandingMetrics:
    if not 1 <= max_workers <= 4:
        raise ValueError("max_workers must be between 1 and 4")
    if not 1 <= max_filings_per_company <= 50:
        raise ValueError("max_filings_per_company must be between 1 and 50")
    metrics = SecLandingMetrics(companies=len(targets))
    filing_tasks: list[tuple[CompanyTarget, FilingRecord]] = []
    for target in targets:
        submissions = store.cached_snapshot("submissions", target.cik, snapshot_ttl)
        if submissions is None:
            payload, response = client.get_submissions(target.cik)
            _, created = store.land_snapshot("submissions", target, response)
            metrics.submissions_landed += int(created)
        else:
            metrics.cached_requests += 1
            payload = json.loads(Path(submissions["landing_path"]).read_text(encoding="utf-8"))

        facts = store.cached_snapshot("companyfacts", target.cik, snapshot_ttl)
        if facts is None:
            _, response = client.get_company_facts(target.cik)
            _, created = store.land_snapshot("companyfacts", target, response)
            metrics.company_facts_landed += int(created)
        else:
            metrics.cached_requests += 1

        filing_tasks.extend((target, filing) for filing in parse_recent_filings(payload, max_filings_per_company))

    def fetch_filing(target: CompanyTarget, filing: FilingRecord) -> bool:
        if store.filing_manifest(target, filing) is not None:
            return False
        response = client.get_filing_document(target.cik, filing.accession_number, filing.primary_document)
        _, created = store.land_filing(target, filing, response)
        return created

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(fetch_filing, target, filing): filing for target, filing in filing_tasks}
        for future in as_completed(futures):
            try:
                if future.result():
                    metrics.filing_documents_landed += 1
                else:
                    metrics.filing_documents_cached += 1
            except Exception:
                metrics.failures += 1
    metrics.http_attempts = client.http_attempts
    metrics.retries = client.retries
    return metrics


def parse_company(value: str) -> CompanyTarget:
    try:
        ticker, cik = value.split(":", 1)
    except ValueError as error:
        raise argparse.ArgumentTypeError("company must use TICKER:CIK") from error
    try:
        return CompanyTarget(ticker.strip().upper(), cik.strip())
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--schema", required=True)
    parser.add_argument("--volume", required=True)
    parser.add_argument("--raw-root", type=Path)
    parser.add_argument("--profile")
    parser.add_argument("--company", action="append", type=parse_company, dest="companies")
    parser.add_argument("--max-filings-per-company", type=int, default=6)
    parser.add_argument("--max-workers", type=int, default=2)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    targets = args.companies or [CompanyTarget("AAPL", "0000320193"), CompanyTarget("MSFT", "0000789019")]
    raw_root = args.raw_root or Path(f"/Volumes/{args.catalog}/{args.schema}/{args.volume}")
    client = SecClient(databricks_profile=args.profile)
    metrics = run_sec_landing(
        targets,
        client,
        SecLandingStore(raw_root),
        max_filings_per_company=args.max_filings_per_company,
        max_workers=args.max_workers,
    )
    print(json.dumps(asdict(metrics), sort_keys=True))
    return 1 if metrics.failures else 0


if __name__ == "__main__":
    exit_code = main()
    if exit_code:
        raise SystemExit(exit_code)
