"""Synchronous off-platform Supervisor transport with SDK-refreshed auth.

No browser credentials, CLI harness, raw event logging, or automatic retries.
The caller must supply server-owned bounded history and persist terminal state.
"""

from __future__ import annotations

import os
import queue
import re
import threading
import time

import requests

from dashboard.supervisor_protocol import ProtocolError, ResponseState, decode_events
from shared.databricks_auth import databricks_config


class SupervisorError(RuntimeError):
    """Public-safe dependency error category."""


# Unresponsive upstream readers retain their slot until they actually exit.
# This bounds abandoned threads as well as active requests within each worker.
_TRANSPORT_SLOTS = threading.BoundedSemaphore(4)


class SupervisorClient:
    def __init__(self, *, config=None, session=None, endpoint=None, clock=time.monotonic,
                 deadline_seconds=180):
        self.config = config
        self.session = session
        self.endpoint = endpoint or os.getenv("SIGNAL_DESK_SUPERVISOR_ENDPOINT", "")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", self.endpoint):
            raise SupervisorError("supervisor_not_configured")
        self.clock = clock
        if not 0 < deadline_seconds <= 180:
            raise ValueError("invalid_deadline")
        self.deadline_seconds = deadline_seconds

    def stream(self, history: list[dict], state: ResponseState):
        """Yield only visible text deltas; completion is inspected through state.

        Network I/O runs in a bounded daemon worker. The caller stops waiting at
        the deadline even during authentication, POST or slow-drip reads. Remote
        cancellation is not guaranteed; an abandoned reader retains its slot.
        """
        started = self.clock()
        slots = _TRANSPORT_SLOTS
        if not slots.acquire(blocking=False):
            raise SupervisorError("dependency_capacity")
        pending = queue.Queue(maxsize=1)
        stopped = threading.Event()

        def publish(kind, value=None):
            while not stopped.is_set():
                try:
                    pending.put((kind, value), timeout=0.05)
                    return
                except queue.Full:
                    continue

        def read():
            events = self._events(history, started)
            try:
                for event in events:
                    if stopped.is_set():
                        break
                    publish("event", event)
                publish("end")
            except SupervisorError as exc:
                publish("error", exc)
            except Exception:
                publish("error", SupervisorError("dependency_unavailable"))
            finally:
                try:
                    events.close()
                finally:
                    slots.release()

        worker = threading.Thread(target=read, name="supervisor-transport", daemon=True)
        try:
            worker.start()
        except Exception:
            slots.release()
            raise
        try:
            while True:
                remaining = self.deadline_seconds - (self.clock() - started)
                if remaining <= 0:
                    raise SupervisorError("deadline_exceeded")
                try:
                    kind, value = pending.get(timeout=remaining)
                except queue.Empty:
                    raise SupervisorError("deadline_exceeded") from None
                if self.clock() - started >= self.deadline_seconds:
                    raise SupervisorError("deadline_exceeded")
                if kind == "end":
                    return
                if kind == "error":
                    raise value
                try:
                    delta = state.accept(value)
                except ProtocolError:
                    raise SupervisorError("invalid_stream") from None
                if delta is not None:
                    yield delta
        finally:
            stopped.set()

    def _events(self, history, started):
        config = self.config or databricks_config()
        owns_session = self.session is None
        session = self.session or requests.Session()
        response = None
        try:
            response = session.post(
                f"{config.host.rstrip('/')}/serving-endpoints/{self.endpoint}/invocations",
                headers={**config.authenticate(), "Content-Type": "application/json", "Accept": "text/event-stream"},
                json={"input": history, "stream": True}, stream=True,
                timeout=(10, 15), allow_redirects=False,
            )
            if response.status_code != 200:
                category = {401: "dependency_auth", 403: "dependency_permission", 429: "dependency_capacity"}.get(
                    response.status_code, "dependency_unavailable")
                raise SupervisorError(category)
            if "text/event-stream" not in response.headers.get("Content-Type", "").lower():
                raise SupervisorError("invalid_stream")
            response.encoding = "utf-8"

            def lines():
                for line in response.iter_lines(chunk_size=1024, decode_unicode=True):
                    if self.clock() - started >= self.deadline_seconds:
                        raise SupervisorError("deadline_exceeded")
                    yield line

            yield from decode_events(lines())
        except requests.Timeout:
            raise SupervisorError("dependency_timeout") from None
        except requests.RequestException:
            raise SupervisorError("dependency_unavailable") from None
        except ProtocolError:
            raise SupervisorError("invalid_stream") from None
        finally:
            if response is not None:
                response.close()
            if owns_session:
                session.close()
