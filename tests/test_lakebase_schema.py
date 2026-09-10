from __future__ import annotations

import pytest

from mcp_server import lakebase


class FakeCursor:
    def __init__(self, executions: list[tuple[object, object]], schema_exists: bool) -> None:
        self.executions = executions
        self.schema_exists = schema_exists

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def execute(self, statement, params=None) -> None:
        self.executions.append((statement, params))

    def fetchone(self) -> dict[str, bool]:
        return {"schema_exists": self.schema_exists}


class FakeConnection:
    def __init__(self, schema_exists: bool = True) -> None:
        self.executions: list[tuple[object, object]] = []
        self.closed = False
        self.schema_exists = schema_exists

    def cursor(self) -> FakeCursor:
        return FakeCursor(self.executions, self.schema_exists)

    def close(self) -> None:
        self.closed = True


def test_student_schema_is_the_provisional_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SIGNAL_DESK_SCHEMA", raising=False)
    assert lakebase.get_schema_name() == "student_sri"


@pytest.mark.parametrize("schema", ["public;DROP SCHEMA public", "Student-Sri", "", "student sri"])
def test_schema_rejects_unsafe_identifiers(monkeypatch: pytest.MonkeyPatch, schema: str) -> None:
    monkeypatch.setenv("SIGNAL_DESK_SCHEMA", schema)
    with pytest.raises(ValueError, match="lowercase PostgreSQL identifier"):
        lakebase.get_schema_name()


def test_connection_sets_student_schema_search_path(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_connection = FakeConnection()
    monkeypatch.setenv("SIGNAL_DESK_SCHEMA", "student_sri")
    monkeypatch.setenv("LAKEBASE_URL", "postgresql://unused")
    monkeypatch.setattr(lakebase.psycopg2, "connect", lambda *_args, **_kwargs: fake_connection)

    with lakebase.get_connection() as opened:
        assert opened is fake_connection

    assert fake_connection.executions == [
        (
            "SELECT EXISTS(SELECT 1 FROM pg_namespace WHERE nspname = %s) AS schema_exists",
            ("student_sri",),
        ),
        ("SELECT set_config('search_path', %s, false)", ("student_sri,public",)),
    ]
    assert fake_connection.closed is True


def test_connection_fails_instead_of_falling_back_to_public(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_connection = FakeConnection(schema_exists=False)
    monkeypatch.setenv("SIGNAL_DESK_SCHEMA", "student_sri")
    monkeypatch.setenv("LAKEBASE_URL", "postgresql://unused")
    monkeypatch.setattr(lakebase.psycopg2, "connect", lambda *_args, **_kwargs: fake_connection)

    with pytest.raises(RuntimeError, match="Required Lakebase schema 'student_sri' does not exist"):
        with lakebase.get_connection():
            pass

    assert fake_connection.closed is True
