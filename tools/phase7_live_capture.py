"""Capture deployed Phase 7 Supervisor results for deterministic scoring."""

from __future__ import annotations

import argparse
import json
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_FIXTURES = Path(__file__).resolve().parents[1] / "agent" / "evaluations.json"
WRITE_TOOLS = {"update_watchlist", "save_research_note", "save_analysis_report"}


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def oauth_token(profile: str) -> str:
    completed = subprocess.run(
        ["databricks", "auth", "token", "--profile", profile],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    token = payload.get("access_token")
    if not isinstance(token, str) or not token:
        raise RuntimeError("Databricks CLI did not return an OAuth access token")
    return token


def request_input(case: dict[str, Any]) -> list[dict[str, str]]:
    if case["id"] == "report_confirmed_write":
        return [
            {
                "role": "user",
                "content": (
                    "Prepare a report titled Cloud comparison for MSFT and AMZN. "
                    "Use this final report text: MSFT and AMZN both compete in cloud "
                    "infrastructure; compare only sourced evidence and retain the usual "
                    "research-risk disclaimer."
                ),
            },
            {
                "role": "assistant",
                "content": (
                    "The final report text is ready. I will save it only after your "
                    "explicit confirmation."
                ),
            },
            {"role": "user", "content": case["prompt"]},
        ]
    return [{"role": "user", "content": case["prompt"]}]


def invoke(
    *,
    host: str,
    endpoint: str,
    token: str,
    input_items: list[dict[str, str]],
    timeout: int,
    long_task: bool,
    trace_events: bool = False,
) -> dict[str, Any]:
    request_body: dict[str, Any] = {"input": input_items, "stream": True}
    if long_task:
        request_body["databricks_options"] = {"long_task": True}
    body = json.dumps(request_body).encode("utf-8")
    request = urllib.request.Request(
        f"{host.rstrip('/')}/serving-endpoints/{endpoint}/invocations",
        data=body,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    def hard_timeout(_signum: int, _frame: Any) -> None:
        raise TimeoutError(f"Supervisor request exceeded {timeout} seconds")

    previous_handler = signal.signal(signal.SIGALRM, hard_timeout)
    signal.alarm(timeout)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            output: list[dict[str, Any]] = []
            response_id: str | None = None
            for raw_line in response:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line.startswith("data:"):
                    continue
                data = line.removeprefix("data:").strip()
                if not data or data == "[DONE]":
                    continue
                event = json.loads(data)
                if trace_events:
                    item = event.get("item") if isinstance(event.get("item"), dict) else {}
                    print(
                        json.dumps(
                            {
                                "event": event.get("type"),
                                "item_type": item.get("type"),
                                "tool": item.get("name"),
                            }
                        ),
                        file=sys.stderr,
                        flush=True,
                    )
                if event.get("error_code"):
                    raise RuntimeError(str(event.get("message") or event["error_code"]))
                if event.get("type") == "response.output_item.done":
                    item = event.get("item")
                    if isinstance(item, dict):
                        output.append(item)
                    response_id = str(event.get("response_id") or event.get("id") or response_id or "")
                if event.get("type") == "response.completed":
                    completed = event.get("response")
                    if isinstance(completed, dict):
                        return completed
                    return {"id": response_id, "status": "completed", "output": output}
                if event.get("type") in {"error", "response.failed"}:
                    raise RuntimeError(str(event.get("message") or event.get("error") or event))
            if output:
                payload = {"id": response_id, "status": "completed", "output": output}
            else:
                raise RuntimeError("Supervisor stream ended without output items")
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous_handler)
    if not isinstance(payload, dict):
        raise RuntimeError("Supervisor response was not a JSON object")
    return payload


def normalized_tool_name(name: str) -> str:
    return name.rsplit("__", 1)[-1]


def capture_case(case: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
    calls: list[dict[str, Any]] = []
    answers: list[str] = []
    for item in response.get("output", []):
        if not isinstance(item, dict):
            continue
        if item.get("type") == "function_call":
            arguments = item.get("arguments", {})
            if isinstance(arguments, str):
                arguments = json.loads(arguments)
            calls.append(
                {
                    "tool": normalized_tool_name(str(item.get("name", ""))),
                    "arguments": arguments,
                }
            )
        if item.get("type") == "message" and item.get("role") == "assistant":
            for content in item.get("content", []):
                if isinstance(content, dict) and content.get("type") == "output_text":
                    answers.append(str(content.get("text", "")))
    return {
        "id": case["id"],
        "response_id": response.get("id"),
        "status": response.get("status"),
        "tool_calls": calls,
        "final_answer": "\n".join(answers),
    }


def write_checkpoint(path: Path, captured: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps({"cases": captured}, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--host", required=True)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--case", action="append", dest="case_ids")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--allow-writes", action="store_true")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--no-long-task", action="store_true")
    parser.add_argument("--trace-events", action="store_true")
    args = parser.parse_args()

    fixtures = load_json(args.fixtures)
    selected = set(args.case_ids or [])
    all_cases = fixtures["cases"]
    cases = [case for case in all_cases if not selected or case["id"] in selected]
    unknown = selected - {case["id"] for case in cases}
    if unknown:
        raise ValueError(f"unknown case ids: {sorted(unknown)}")
    if not args.allow_writes:
        write_cases = [
            case["id"]
            for case in cases
            if any(call.get("tool") in WRITE_TOOLS for call in case.get("expected_calls", []))
        ]
        if write_cases:
            raise RuntimeError(
                "write cases selected; rerun with --allow-writes after confirming the target: "
                + ", ".join(write_cases)
            )

    captured: list[dict[str, Any]] = []
    if args.resume and args.output.exists():
        existing = load_json(args.output).get("cases", [])
        captured = [case for case in existing if isinstance(case, dict)]
        if not selected:
            captured_ids = {case.get("id") for case in captured}
            cases = [case for case in cases if case["id"] not in captured_ids]

    token = oauth_token(args.profile)
    case_order = {case["id"]: index for index, case in enumerate(all_cases)}
    for case in cases:
        for attempt in range(args.retries + 1):
            try:
                response = invoke(
                    host=args.host,
                    endpoint=args.endpoint,
                    token=token,
                    input_items=request_input(case),
                    timeout=args.timeout,
                    long_task=not args.no_long_task,
                    trace_events=args.trace_events,
                )
                captured = [item for item in captured if item.get("id") != case["id"]]
                captured.append(capture_case(case, response))
                captured.sort(key=lambda item: case_order.get(item.get("id"), len(case_order)))
                write_checkpoint(args.output, captured)
                break
            except (
                TimeoutError,
                urllib.error.URLError,
                urllib.error.HTTPError,
                json.JSONDecodeError,
                RuntimeError,
            ):
                if attempt == args.retries:
                    raise
                time.sleep(2**attempt)
        print(json.dumps({"id": case["id"], "captured": True}), flush=True)

    write_checkpoint(args.output, captured)
    print(json.dumps({"output": str(args.output), "cases": len(captured)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
