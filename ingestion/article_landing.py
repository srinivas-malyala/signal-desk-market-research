"""Land content-addressed Massive news responses for article/ticker normalization."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

if __package__ in {None, ""}:
    runtime_file = globals().get("__file__") or globals().get("filename")
    if runtime_file:
        sys.path.insert(0, str(Path(runtime_file).resolve().parents[1]))

from ingestion.market_backfill import _canonical_json_bytes, atomic_write  # noqa: E402
from mcp_server.massive_client import MassiveClient, build_rate_limiter  # noqa: E402
from shared.contracts.models import Ticker  # noqa: E402


@dataclass
class ArticleLandingMetrics:
    query_tickers: int = 0
    api_calls: int = 0
    cached_queries: int = 0
    landed_articles: int = 0
    landed_bytes: int = 0


class ArticleLandingStore:
    def __init__(self, raw_root: Path, clock=lambda: datetime.now(UTC)) -> None:
        self.root = raw_root / "research_articles"
        self.clock = clock

    def cached(self, ticker: str, max_age: timedelta) -> dict | None:
        path = self.root / f"query_ticker={ticker}" / "cache.json"
        if not path.exists():
            return None
        cache = json.loads(path.read_text(encoding="utf-8"))
        if self.clock() - datetime.fromisoformat(cache["checked_at"]) > max_age:
            return None
        manifest_path = Path(cache["manifest_path"])
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        payload = Path(manifest["landing_path"]).read_bytes()
        if hashlib.sha256(payload).hexdigest() != manifest["checksum_sha256"]:
            raise ValueError(f"Article landing checksum mismatch for {ticker}")
        return manifest

    def land(self, ticker: str, response) -> tuple[dict, bool]:
        content = _canonical_json_bytes(response.payload)
        checksum = hashlib.sha256(content).hexdigest()
        directory = self.root / f"query_ticker={ticker}" / f"checksum={checksum}"
        data_path = directory / "response.json"
        manifest_path = directory / "manifest.json"
        created = not manifest_path.exists()
        if created:
            atomic_write(data_path, content)
            results = response.payload.get("results", [])
            manifest = {
                "version": 1,
                "source": "massive",
                "kind": "news_query",
                "query_ticker": ticker,
                "request_id": response.observation.massive_request_id,
                "correlation_id": response.observation.correlation_id,
                "status_code": response.observation.status_code,
                "row_count": len(results) if isinstance(results, list) else 0,
                "byte_count": len(content),
                "checksum_sha256": checksum,
                "fetched_at": self.clock().isoformat(),
                "landing_path": str(data_path),
            }
            atomic_write(manifest_path, _canonical_json_bytes(manifest))
        else:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not data_path.exists() or hashlib.sha256(data_path.read_bytes()).hexdigest() != checksum:
                raise ValueError(f"Incomplete article landing pair for {ticker}")
        cache = {
            "version": 1,
            "checked_at": self.clock().isoformat(),
            "manifest_path": str(manifest_path),
        }
        atomic_write(directory.parent / "cache.json", _canonical_json_bytes(cache))
        return manifest, created


def run_article_landing(
    tickers: list[str],
    client: MassiveClient,
    store: ArticleLandingStore,
    *,
    limit: int = 50,
    cache_ttl: timedelta = timedelta(hours=6),
) -> ArticleLandingMetrics:
    if not 1 <= limit <= 1000:
        raise ValueError("limit must be between 1 and 1000")
    symbols = list(dict.fromkeys(Ticker(symbol=value).symbol for value in tickers))
    metrics = ArticleLandingMetrics(query_tickers=len(symbols))
    for symbol in symbols:
        cached = store.cached(symbol, cache_ttl)
        if cached is not None:
            metrics.cached_queries += 1
            metrics.landed_articles += int(cached["row_count"])
            continue
        response = client.get_with_metadata(
            "/v2/reference/news",
            {
                "ticker": symbol,
                "limit": limit,
                "order": "desc",
                "sort": "published_utc",
            },
        )
        manifest, _ = store.land(symbol, response)
        metrics.api_calls += 1
        metrics.landed_articles += int(manifest["row_count"])
        metrics.landed_bytes += int(manifest["byte_count"])
    return metrics


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--schema", required=True)
    parser.add_argument("--volume", required=True)
    parser.add_argument("--raw-root", type=Path)
    parser.add_argument("--profile")
    parser.add_argument(
        "--rate-limit-backend",
        choices=("process", "lakebase"),
        default=os.getenv("MASSIVE_RATE_LIMIT_BACKEND", "process"),
    )
    parser.add_argument("--ticker", action="append", dest="tickers")
    parser.add_argument("--limit", type=int, default=50)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    raw_root = args.raw_root or Path(f"/Volumes/{args.catalog}/{args.schema}/{args.volume}")
    limiter = build_rate_limiter(
        args.rate_limit_backend,
        state_path=raw_root / "_control" / "massive_rate_limit.json",
    )
    client = MassiveClient(limiter=limiter, databricks_profile=args.profile)
    metrics = run_article_landing(
        args.tickers or ["AAPL", "MSFT"],
        client,
        ArticleLandingStore(raw_root),
        limit=args.limit,
    )
    print(json.dumps({**asdict(metrics), **client.metrics()}, sort_keys=True))
    return 0


if __name__ == "__main__":
    exit_code = main()
    if exit_code:
        raise SystemExit(exit_code)
