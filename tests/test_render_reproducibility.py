from __future__ import annotations

from tools.check_render_reproducibility import validate_blueprint, validate_locks


def test_render_blueprint_matches_reproducible_contract() -> None:
    validate_blueprint()


def test_render_dependencies_are_hash_pinned_for_linux() -> None:
    validate_locks()
