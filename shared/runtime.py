"""Environment-mode contract shared by local tests and deployed components."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeSettings:
    environment: str
    use_mock_backend: bool

    @classmethod
    def from_environment(cls, environ: Mapping[str, str] | None = None) -> RuntimeSettings:
        values = environ if environ is not None else os.environ
        environment = values.get("SIGNAL_DESK_ENV", "local").strip().lower()
        if environment not in {"local", "test", "dev", "prod"}:
            raise ValueError("SIGNAL_DESK_ENV must be local, test, dev, or prod")
        use_mock = values.get("USE_MOCK_BACKEND", "false").strip().lower() == "true"
        if environment in {"dev", "prod"} and use_mock:
            raise ValueError("mock backends are prohibited in deployed environments")
        return cls(environment=environment, use_mock_backend=use_mock)
