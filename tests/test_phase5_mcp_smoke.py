from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from tools.phase5_mcp_smoke import EXPECTED_TOOLS, _tool_payload, run_mcp_checks, run_render


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.replayed = False

    async def list_tools(self):
        return [SimpleNamespace(name=name) for name in sorted(EXPECTED_TOOLS)]

    async def call_tool_mcp(self, name: str, arguments: dict):
        self.calls.append((name, arguments))
        correlation = f"correlation-{len(self.calls)}"
        if name == "get_stock_performance":
            payload = {
                "status": "success",
                "ticker": "AAPL",
                "as_of": "2026-09-10",
                "source": "Unity Catalog silver_market_bars joined to gold_stock_performance",
                "correlation_id": correlation,
            }
        elif name == "semantic_research":
            payload = {
                "status": "success",
                "matches": [
                    {
                        "source_type": "article",
                        "source_id": "source-1",
                        "ticker": "AAPL",
                        "title": "Apple production",
                    }
                ],
                "correlation_id": correlation,
            }
        elif name == "get_watchlist":
            payload = {"status": "success", "tickers": [], "correlation_id": correlation}
        else:
            key = arguments["idempotency_key"]
            if arguments["action"] == "remove" and not key.startswith("phase5-cleanup-"):
                payload = {
                    "status": "error",
                    "message": "idempotency_key was already used for different request parameters.",
                    "correlation_id": correlation,
                }
            else:
                replay = self.replayed and arguments["action"] == "add"
                self.replayed = self.replayed or arguments["action"] == "add"
                payload = {
                    "status": "success",
                    "idempotent_replay": replay,
                    "correlation_id": correlation,
                }
        return SimpleNamespace(structuredContent=payload, content=[])


def _trace_reader(correlation_ids: list[str]) -> dict:
    values = sorted(correlation_ids)
    return {
        "trace_count": len(values),
        "event_count": len(values),
        "trace_correlation_ids": values,
        "event_correlation_ids": values,
        "trace_payloads_bounded": True,
        "idempotency_values_redacted": True,
        "event_payloads_bounded": True,
    }


@pytest.mark.parametrize("exercise_writes,expected_calls", [(False, 2), (True, 8)])
def test_post_deployment_checks_are_read_only_by_default_and_reversible_when_enabled(
    exercise_writes: bool,
    expected_calls: int,
) -> None:
    client = FakeClient()
    result = asyncio.run(
        run_mcp_checks(
            client,
            exercise_writes=exercise_writes,
            trace_reader=_trace_reader,
        )
    )
    assert result["status"] == "passed"
    assert len(client.calls) == expected_calls
    writes = [call for call in client.calls if call[0] == "update_watchlist"]
    if exercise_writes:
        assert len(writes) == 4
        assert all(call[1]["confirmed"] is True for call in writes)
        assert result["writes"]["cleanup_proved"] is True
    else:
        assert writes == []


def test_tool_payload_accepts_structured_fastmcp_result() -> None:
    assert _tool_payload(SimpleNamespace(structuredContent={"status": "success"}, content=[])) == {
        "status": "success"
    }


def test_write_smoke_attempts_cleanup_when_replay_call_fails() -> None:
    class FailingReplayClient(FakeClient):
        async def call_tool_mcp(self, name: str, arguments: dict):
            prior_adds = [
                call
                for call in self.calls
                if call[0] == "update_watchlist" and call[1]["action"] == "add"
            ]
            if name == "update_watchlist" and arguments["action"] == "add" and prior_adds:
                self.calls.append((name, arguments))
                raise RuntimeError("simulated retry transport failure")
            return await super().call_tool_mcp(name, arguments)

    client = FailingReplayClient()
    with pytest.raises(RuntimeError, match="simulated retry"):
        asyncio.run(run_mcp_checks(client, exercise_writes=True, trace_reader=_trace_reader))
    cleanup_calls = [
        call
        for call in client.calls
        if call[0] == "update_watchlist"
        and call[1]["action"] == "remove"
        and call[1]["idempotency_key"].startswith("phase5-cleanup-")
    ]
    assert len(cleanup_calls) == 1


def test_harness_never_forges_forwarded_identity_headers() -> None:
    source = (__import__("pathlib").Path(__file__).parents[1] / "tools" / "phase5_mcp_smoke.py").read_text()
    assert "x-forwarded-email" not in source.lower()
    assert "x-forwarded-user" not in source.lower()
    assert "x-forwarded-access-token" not in source.lower()


def test_render_harness_rejects_unsafe_url_and_short_machine_token() -> None:
    with pytest.raises(ValueError, match="must be HTTPS"):
        asyncio.run(
            run_render(
                service_url="http://mcp.example.test",
                bearer_token="x" * 40,
                exercise_writes=False,
                timeout_seconds=10,
            )
        )
    with pytest.raises(ValueError, match="missing or invalid"):
        asyncio.run(
            run_render(
                service_url="https://mcp.example.test",
                bearer_token="short",
                exercise_writes=False,
                timeout_seconds=10,
            )
        )
