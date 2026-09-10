from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

from ingestion.article_landing import ArticleLandingStore, run_article_landing
from mcp_server.massive_client import MassiveResponse, RequestObservation


def response() -> MassiveResponse:
    return MassiveResponse(
        payload={
            "status": "OK",
            "request_id": "request-1",
            "results": [
                {
                    "id": "article-1",
                    "title": "Two-company story",
                    "tickers": ["AAPL", "MSFT"],
                    "published_utc": "2026-09-09T12:00:00Z",
                    "article_url": "https://example.com/story",
                }
            ],
        },
        observation=RequestObservation("correlation-1", "request-1", 200, 20, 100, 1, 1),
    )


def test_article_queries_are_content_addressed_and_cached(tmp_path: Path) -> None:
    client = Mock()
    client.get_with_metadata.return_value = response()
    store = ArticleLandingStore(tmp_path)
    first = run_article_landing(["aapl", "AAPL"], client, store)
    assert first.query_tickers == 1
    assert first.api_calls == 1
    assert first.landed_articles == 1

    second_client = Mock()
    second = run_article_landing(["AAPL"], second_client, store)
    assert second.cached_queries == 1
    assert second.landed_articles == 1
    second_client.get_with_metadata.assert_not_called()


def test_article_payload_retains_all_tickers(tmp_path: Path) -> None:
    store = ArticleLandingStore(tmp_path)
    manifest, created = store.land("AAPL", response())
    assert created is True
    payload = Path(manifest["landing_path"]).read_text(encoding="utf-8")
    assert '"tickers":["AAPL","MSFT"]' in payload
