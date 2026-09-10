from __future__ import annotations

import pytest

from shared.runtime import RuntimeSettings


def test_local_mock_backend_is_explicitly_supported() -> None:
    settings = RuntimeSettings.from_environment(
        {"SIGNAL_DESK_ENV": "test", "USE_MOCK_BACKEND": "true"}
    )
    assert settings.use_mock_backend is True


def test_deployed_mock_backend_fails_closed() -> None:
    with pytest.raises(ValueError, match="prohibited"):
        RuntimeSettings.from_environment(
            {"SIGNAL_DESK_ENV": "prod", "USE_MOCK_BACKEND": "true"}
        )
