"""Synchronous off-platform Supervisor transport with SDK-refreshed auth.

No browser credentials, CLI harness, raw event logging, or automatic retries.
The caller must supply server-owned bounded history and persist terminal state.
"""

from __future__ import annotations

import os
import re
import time

import requests

from dashboard.supervisor_protocol import ProtocolError, ResponseState, decode_events
from shared.databricks_auth import databricks_config


class SupervisorError(RuntimeError):
    """Public-safe dependency error category."""


class SupervisorClient:
    def __init__(self, *, config=None, session=None, endpoint=None, clock=time.monotonic):
        self.config = config
        self.session = session
        self.endpoint = endpoint or os.getenv("SIGNAL_DESK_SUPERVISOR_ENDPOINT", "")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", self.endpoint):
            raise SupervisorError("supervisor_not_configured")
        self.clock = clock

    def stream(self, history: list[dict], state: ResponseState):
        """Yield only visible text deltas; completion is inspected through state.

        Total deadline is checked between frames; a 15-second socket inactivity
        timeout bounds blocking reads. A full wall-clock watchdog remains a
        rollout gate before claiming a strict deadline under slow-drip traffic.
        """
        started = self.clock()
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
                    if self.clock() - started > 180:
                        raise SupervisorError("deadline_exceeded")
                    yield line

            for event in decode_events(lines()):
                delta = state.accept(event)
                if delta is not None:
                    yield delta
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
