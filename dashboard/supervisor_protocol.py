"""Bounded Supervisor SSE parser independent of the CLI capture harness.

    This module is not a public-event renderer. Raw tool data remains private;
    later proposal/citation validation must precede exposing executable content.
"""

from __future__ import annotations

import json
from collections.abc import Iterable

MAX_STREAM_BYTES = 2_000_000
MAX_FRAME_BYTES = 256_000
MAX_TEXT_BYTES = 100_000


class ProtocolError(ValueError):
    """Safe protocol category; never includes upstream payloads."""


def decode_events(lines: Iterable[str]):
    total = 0
    frame = []
    frame_size = 0

    def decode():
        payload = "\n".join(frame)
        if payload == "[DONE]":
            return {"type": "transport.done"}
        try:
            event = json.loads(payload)
        except ValueError:
            raise ProtocolError("invalid_event") from None
        if not isinstance(event, dict):
            raise ProtocolError("invalid_event")
        return event

    for line in lines:
        total += len(line.encode("utf-8")) + 1
        if total > MAX_STREAM_BYTES:
            raise ProtocolError("stream_limit")
        line = line.rstrip("\r\n")
        if line.startswith("data:"):
            value = line[5:].lstrip(" ")
            frame_size += len(value.encode("utf-8")) + 1
            if frame_size > MAX_FRAME_BYTES:
                raise ProtocolError("event_limit")
            frame.append(value)
        elif not line and frame:
            yield decode()
            frame, frame_size = [], 0
    # An unterminated data frame is not trusted as a terminal marker.
    if frame:
        raise ProtocolError("truncated_frame")


class ResponseState:
    """Completion requires finalized assistant text and an observed terminal."""

    def __init__(self):
        self.text = ""
        self.final_text = ""
        self.failed = False
        self.terminal = False
        self.finalized = False
        self.seen = set()

    def accept(self, event: dict) -> str | None:
        if not isinstance(event, dict):
            raise ProtocolError("invalid_event")
        kind = event.get("type")
        if kind in {"error", "response.failed", "response.incomplete"}:
            self.failed = True
        if kind == "response.output_text.delta":
            delta = event.get("delta")
            if not isinstance(delta, str):
                raise ProtocolError("invalid_text")
            self.text += delta
            if len(self.text.encode("utf-8")) > MAX_TEXT_BYTES:
                raise ProtocolError("text_limit")
            return delta
        if kind == "response.output_item.done":
            item = event.get("item") or {}
            if not isinstance(item, dict):
                raise ProtocolError("invalid_item")
            identity = (item.get("type"), item.get("id"))
            if not all(value is None or isinstance(value, str) for value in identity):
                raise ProtocolError("invalid_item")
            if identity in self.seen:
                return None
            self.seen.add(identity)
            if item.get("type") == "message" and item.get("role") == "assistant":
                content = item.get("content", [])
                if not isinstance(content, list) or any(not isinstance(part, dict) for part in content):
                    raise ProtocolError("invalid_content")
                parts = [part.get("text") for part in content if part.get("type") == "output_text"]
                if any(not isinstance(part, str) for part in parts):
                    raise ProtocolError("invalid_text")
                text = "".join(parts)
                if len(text.encode("utf-8")) > MAX_TEXT_BYTES:
                    raise ProtocolError("text_limit")
                self.final_text = text
                self.finalized = bool(text) and item.get("status") not in {"incomplete", "failed"}
        if kind == "transport.done":
            self.terminal = self.finalized
        if kind == "response.completed":
            response = event.get("response") or {}
            if not isinstance(response, dict):
                raise ProtocolError("invalid_response")
            if response.get("status") == "completed":
                output = response.get("output", [])
                if not isinstance(output, list):
                    raise ProtocolError("invalid_response")
                for item in output:
                    self.accept({"type": "response.output_item.done", "item": item})
                self.terminal = self.finalized
        return None

    @property
    def status(self) -> str:
        if self.failed:
            return "failed"
        return "completed" if self.terminal and self.finalized else "interrupted"
