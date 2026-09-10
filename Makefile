.PHONY: install test lint phase0-feasibility

install:
	uv sync --extra dashboard --dev

test:
	uv run pytest -m "not integration and not e2e"

lint:
	uv run ruff check shared tools tests mcp_server/tests

phase0-feasibility:
	uv run python tools/phase0_feasibility.py
