"""M0 protocol evidence collector. CLI only; never imported by web requests.

Reports structural metadata, not transcripts, tokens, source contents, or tool
argument values. Live requests are fixed research/formatting probes.
"""

from __future__ import annotations

import argparse
import json
import signal
import time
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

from tools.phase7_live_capture import oauth_token

MAX_CAPTURE_BYTES = 2_000_000
MAX_EVENT_BYTES = 256_000
RESEARCH_TOOLS = {
    "get_stock_performance", "get_company_research", "compare_stocks", "semantic_research",
}


def sse_events(lines: Iterable[str]) -> Iterable[dict[str, Any]]:
    """Decode SSE data frames, including multiline data and terminal EOF frames."""
    data: list[str] = []
    total = 0
    frame_bytes = 0
    for line in lines:
        size = len(line.encode("utf-8"))
        total += size
        if total > MAX_CAPTURE_BYTES:
            raise ValueError("capture_limit")
        line = line.rstrip("\r\n")
        if line.startswith("data:"):
            value = line[5:].lstrip(" ")
            frame_bytes += len(value.encode("utf-8"))
            if frame_bytes > MAX_EVENT_BYTES:
                raise ValueError("event_limit")
            data.append(value)
        if not line and data:
            payload = "\n".join(data)
            data, frame_bytes = [], 0
            if payload != "[DONE]":
                event = json.loads(payload)
                if not isinstance(event, dict):
                    raise ValueError("invalid_event")
                yield event
            else:
                yield {"type": "transport.done"}
    if data:
        if "\n".join(data) == "[DONE]":
            yield {"type": "transport.done"}
        else:
            event = json.loads("\n".join(data))
            if not isinstance(event, dict):
                raise ValueError("invalid_event")
            yield event


def summarize(events: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Return allowlisted structural evidence only; EOF is not completion."""
    types: Counter[str] = Counter()
    item_types: Counter[str] = Counter()
    item_statuses: Counter[str] = Counter()
    tool_calls: list[dict[str, Any]] = []
    text_lengths: list[int] = []
    annotation_types: Counter[str] = Counter()
    envelope_shapes: list[bool] = []
    completion = False
    failed = False
    last_item_kind = ""
    seen_items: set[tuple[str, str]] = set()

    def inspect_item(item: dict[str, Any]) -> None:
        nonlocal last_item_kind
        item_id = str(item.get("id") or "")
        kind = str(item.get("type") or "unknown")
        identity = (kind, item_id)
        if item_id and identity in seen_items:
            return
        if item_id:
            seen_items.add(identity)
        item_types[kind] += 1
        last_item_kind = kind if item.get("role") != "assistant" else "assistant_message"
        item_statuses[str(item.get("status") or "absent")] += 1
        if kind == "function_call":
            name = str(item.get("name") or "").rsplit("__", 1)[-1]
            arguments = item.get("arguments", {})
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except ValueError:
                    arguments = None
            tool_calls.append({
                "tool": name if name in RESEARCH_TOOLS else "other_tool",
                "research_allowlisted": name in RESEARCH_TOOLS,
                "argument_types": {
                    key: type(value).__name__ for key, value in arguments.items()
                    if key in {"ticker", "tickers", "query", "source_types", "start_date", "end_date", "lookback_days"}
                } if isinstance(arguments, dict) else None,
            })
        if kind == "message" and item.get("role") == "assistant":
            for content in item.get("content", []):
                if isinstance(content, dict) and content.get("type") == "output_text":
                    text_lengths.append(len(str(content.get("text") or "")))
                    try:
                        envelope = json.loads(str(content.get("text") or ""))
                    except ValueError:
                        envelope = None
                    envelope_shapes.append(
                        isinstance(envelope, dict)
                        and set(envelope) == {"schema_version", "answer", "proposals"}
                        and envelope.get("schema_version") == "1"
                        and isinstance(envelope.get("answer"), str)
                        and isinstance(envelope.get("proposals"), list)
                    )
                    for annotation in content.get("annotations", []):
                        if isinstance(annotation, dict):
                            annotation_types[str(annotation.get("type") or "unknown")] += 1

    for event in events:
        kind = str(event.get("type") or "unknown")
        types[kind] += 1
        if kind == "response.output_item.done" and isinstance(event.get("item"), dict):
            inspect_item(event["item"])
        if kind == "response.completed":
            response = event.get("response", {})
            completion = isinstance(response, dict) and response.get("status", "completed") == "completed"
            if isinstance(response, dict):
                for item in response.get("output", []):
                    if isinstance(item, dict):
                        inspect_item(item)
        if kind == "transport.done" and last_item_kind == "assistant_message" and text_lengths:
            completion = True
        if kind in {"error", "response.failed", "response.incomplete"} or event.get("error_code"):
            failed = True
    return {
        "event_types": dict(types), "item_types": dict(item_types), "item_statuses": dict(item_statuses),
        "tool_calls": tool_calls, "assistant_text_lengths": text_lengths,
        "annotation_types": dict(annotation_types),
        "envelope_shapes": envelope_shapes,
        "terminal_state": "failed" if failed else "completed" if completion else "interrupted",
    }


def probe_cases() -> dict[str, list[dict[str, str]]]:
    return {
        "filing": [{"role": "user", "content": "Find AAPL filing evidence about services revenue. Use semantic_research with tickers as [\"AAPL\"] and source_types as [\"filing\"]. Do not save or change anything."}],
        "comparison": [{"role": "user", "content": "Compare AAPL and MSFT performance over 30 days. Research only; do not save or change anything."}],
        "multi_turn": [
            {"role": "user", "content": "I want a performance comparison of AAPL and MSFT."},
            {"role": "assistant", "content": "What lookback period should I use?"},
            {"role": "user", "content": "30 days. Research only; do not save or change anything."},
        ],
        "invalid_ticker": [{"role": "user", "content": "Show 30-day performance for INVALID!! without guessing a replacement. Do not save or change anything."}],
        "envelope_format": [{"role": "user", "content": 'Formatting exercise only; do not call tools or perform actions. Return exactly this JSON: {"schema_version":"1","answer":"Draft only","proposals":[]}'}],
    }


def live_summary(host: str, endpoint: str, profile: str, case: str, timeout: int) -> dict[str, Any]:
    parsed = urlparse(host)
    if parsed.scheme != "https" or not parsed.hostname or parsed.path not in {"", "/"} or parsed.query or parsed.fragment or parsed.username:
        raise ValueError("invalid_workspace_origin")
    if not endpoint or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in endpoint):
        raise ValueError("invalid_endpoint")
    token = oauth_token(profile)
    started = time.monotonic()

    def deadline(_signum: int, _frame: Any) -> None:
        raise TimeoutError("total_deadline")

    previous = signal.signal(signal.SIGALRM, deadline)
    signal.alarm(timeout)
    try:
        with requests.post(
            f"{host.rstrip('/')}/serving-endpoints/{endpoint}/invocations",
            headers={"Authorization": f"Bearer {token}"},
            json={"input": probe_cases()[case], "stream": True, "databricks_options": {"long_task": True}},
            stream=True, timeout=(10, min(timeout, 60)),
        ) as response:
            if response.status_code != 200:
                return {"case": case, "http_status": response.status_code, "terminal_state": "http_error"}
            response.encoding = "utf-8"
            result = summarize(sse_events(response.iter_lines(decode_unicode=True)))
            return {"case": case, "elapsed_seconds": round(time.monotonic() - started, 2), **result}
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path, help="Inspect a local SSE capture without exposing contents")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--profile")
    parser.add_argument("--host")
    parser.add_argument("--endpoint")
    parser.add_argument("--case", choices=tuple(probe_cases()), default="filing")
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()
    if bool(args.capture) == args.live:
        parser.error("Choose --capture or --live")
    if not 1 <= args.timeout <= 300:
        parser.error("timeout must be 1–300 seconds")
    if args.live and not all((args.profile, args.host, args.endpoint)):
        parser.error("live requires explicit profile, host, and endpoint")
    try:
        if args.capture:
            with args.capture.open(encoding="utf-8") as handle:
                result = summarize(sse_events(handle))
        else:
            result = live_summary(args.host, args.endpoint, args.profile, args.case, args.timeout)
        print(json.dumps(result, sort_keys=True))
        return 0 if result["terminal_state"] == "completed" else 1
    except (ValueError, OSError, TimeoutError, requests.RequestException) as error:
        print(json.dumps({"terminal_state": "probe_failed", "error_category": type(error).__name__}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
