from __future__ import annotations

import base64
from types import SimpleNamespace

import pytest

from mcp_server import lakebase


class FakeCursor:
    def __init__(self, schemas: tuple[str, ...] = ("bootcamp_students", "bootcamp_cdc")) -> None:
        self.schemas = schemas
        self.executions: list[tuple[object, object]] = []

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def execute(self, statement, params=None) -> None:
        self.executions.append((statement, params))

    def fetchall(self) -> list[dict[str, str]]:
        return [{"nspname": schema} for schema in self.schemas]


class FakeConnection:
    def __init__(self, schemas: tuple[str, ...] = ("bootcamp_students", "bootcamp_cdc")) -> None:
        self.cursor_value = FakeCursor(schemas)

    def cursor(self) -> FakeCursor:
        return self.cursor_value


def test_shared_namespace_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("SIGNAL_DESK_SCHEMA", "SIGNAL_DESK_GRAPH_SCHEMA", "SIGNAL_DESK_TABLE_SUFFIX"):
        monkeypatch.delenv(name, raising=False)
    assert lakebase.get_schema_name() == "bootcamp_students"
    assert lakebase.get_graph_schema_name() == "bootcamp_cdc"
    assert lakebase.get_table_suffix() == "srini"
    assert lakebase.table_name("users") == "bootcamp_students.users_srini"
    assert lakebase.table_name("users", graph=True) == "bootcamp_cdc.users_srini"


@pytest.mark.parametrize(
    ("setting", "getter", "value"),
    [
        ("SIGNAL_DESK_SCHEMA", lakebase.get_schema_name, "public;drop_schema"),
        ("SIGNAL_DESK_GRAPH_SCHEMA", lakebase.get_graph_schema_name, "Bootcamp-CDC"),
        ("SIGNAL_DESK_TABLE_SUFFIX", lakebase.get_table_suffix, "student sri"),
    ],
)
def test_namespace_rejects_unsafe_identifiers(
    monkeypatch: pytest.MonkeyPatch,
    setting: str,
    getter,
    value: str,
) -> None:
    monkeypatch.setenv(setting, value)
    with pytest.raises(ValueError, match="lowercase PostgreSQL identifier"):
        getter()


def test_table_and_index_names_are_allowlisted() -> None:
    with pytest.raises(ValueError, match="Unknown Signal Desk table"):
        lakebase.table_name("other_student_table")
    with pytest.raises(ValueError, match="Unknown Signal Desk index"):
        lakebase.index_name("unsafe_index")


def test_migration_rendering_qualifies_student_objects() -> None:
    rendered = lakebase.render_migration(
        "CREATE TABLE {{table:users}} (id BIGINT); "
        "CREATE INDEX {{index:idx_price_ticker_time}} ON {{table:users}}(id);"
    )
    assert "bootcamp_students.users_srini" in rendered
    assert "bootcamp_students.idx_price_ticker_time_srini" in rendered
    assert "{{" not in rendered


def test_migration_rendering_rejects_unknown_tokens() -> None:
    with pytest.raises(ValueError, match="unknown template token"):
        lakebase.render_migration("SELECT '{{schema}}'")


def test_all_migrations_render_without_schema_ddl() -> None:
    paths = lakebase.migration_paths()
    assert [path.name for path in paths] == [
        "0001_operational_core.sql",
        "0002_agent_operations.sql",
        "0003_cdc_replica_identity.sql",
    ]
    rendered = "\n".join(lakebase.render_migration(path.read_text()) for path in paths)
    assert "CREATE SCHEMA" not in rendered.upper()
    assert "student_sri" not in rendered
    for base in lakebase.TABLE_BASES - {"schema_migrations"}:
        assert f"bootcamp_students.{base}_srini" in rendered


def test_connection_requires_shared_schemas_and_sets_search_path() -> None:
    connection = FakeConnection()
    lakebase.configure_schema(connection)
    assert connection.cursor_value.executions == [
        (
            "SELECT nspname FROM pg_namespace WHERE nspname = ANY(%s)",
            (["bootcamp_students", "bootcamp_cdc"],),
        ),
        ("SELECT set_config('search_path', %s, false)", ("bootcamp_students,public",)),
    ]


def test_connection_fails_when_shared_schema_is_missing() -> None:
    connection = FakeConnection(("bootcamp_students",))
    with pytest.raises(RuntimeError, match="bootcamp_cdc"):
        lakebase.configure_schema(connection)


def test_secret_defaults_are_decoded_in_memory(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LAKEBASE_URL", raising=False)
    monkeypatch.delenv("LAKEBASE_SECRET_SCOPE", raising=False)
    monkeypatch.delenv("LAKEBASE_SECRET_KEY", raising=False)
    calls: list[tuple[str, str]] = []

    class Secrets:
        def get_secret(self, *, scope: str, key: str):
            calls.append((scope, key))
            return SimpleNamespace(value=base64.b64encode(b"postgresql://unused").decode())

    monkeypatch.setattr(lakebase, "WorkspaceClient", lambda: SimpleNamespace(secrets=Secrets()))
    assert lakebase.get_lakebase_url() == "postgresql://unused"
    assert calls == [("database", "lakebase-url")]


@pytest.mark.parametrize(("minimum", "maximum"), [("0", "5"), ("5", "4"), ("1", "21")])
def test_pool_bounds_are_bounded(monkeypatch: pytest.MonkeyPatch, minimum: str, maximum: str) -> None:
    monkeypatch.setenv("LAKEBASE_POOL_MIN", minimum)
    monkeypatch.setenv("LAKEBASE_POOL_MAX", maximum)
    with pytest.raises(ValueError, match="pool bounds"):
        lakebase._pool_bounds()
