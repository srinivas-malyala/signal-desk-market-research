"""Opt-in integration against disposable local PostgreSQL, never Lakebase."""

import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import psycopg2
import pytest
from psycopg2.extras import RealDictCursor

from dashboard.assistant_repository import AssistantConflict, AssistantNotFound, AssistantRepository
from mcp_server.lakebase import render_migration

pytestmark = pytest.mark.integration


@pytest.fixture
def database(monkeypatch):
    port = os.getenv("ASSISTANT_TEST_POSTGRES_PORT")
    if not port:
        pytest.skip("Disposable localhost PostgreSQL port not supplied")
    schema = "assistant_test_" + uuid4().hex
    monkeypatch.setenv("SIGNAL_DESK_SCHEMA", schema)
    monkeypatch.setenv("SIGNAL_DESK_TABLE_SUFFIX", "test")

    def connect():
        return psycopg2.connect(host="127.0.0.1", port=int(port), dbname="postgres", user="postgres",
                                connect_timeout=5, cursor_factory=RealDictCursor)

    with connect() as conn, conn.cursor() as cur:
        cur.execute(f"CREATE SCHEMA {schema}")
        cur.execute(f"CREATE TABLE {schema}.users_test(id BIGINT PRIMARY KEY)")
        cur.execute(f"INSERT INTO {schema}.users_test VALUES(1),(2),(3)")
        # Minimal existing watchlist tables, matching their production keys.
        cur.execute(f"CREATE TABLE {schema}.watchlists_test(id BIGINT PRIMARY KEY, "
                    f"user_id BIGINT REFERENCES {schema}.users_test(id), name TEXT, UNIQUE(user_id,name))")
        cur.execute(f"CREATE TABLE {schema}.watchlist_tickers_test(watchlist_id BIGINT "
                    f"REFERENCES {schema}.watchlists_test(id), ticker TEXT, PRIMARY KEY(watchlist_id,ticker))")
        sql = render_migration((Path(__file__).parents[1] / "mcp_server/migrations/0006_assistant_conversations.sql").read_text())
        cur.execute(sql)
        cur.execute(sql)  # Repeatable additive DDL.

    @contextmanager
    def connection():
        conn = connect()
        try:
            yield conn
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    try:
        yield AssistantRepository(connection), connection
    finally:
        # Only this fixture's validated UUID-named schema is removed.
        with connect() as conn, conn.cursor() as cur:
            cur.execute(f"DROP SCHEMA {schema} CASCADE")


def test_real_owner_isolation_and_roundtrip(database):
    repo, _ = database
    conversation = repo.create(1)
    assert not repo.list_conversations(2)
    with pytest.raises(AssistantNotFound):
        repo.turns(2, conversation["id"])
    with pytest.raises(AssistantNotFound):
        repo.start(2, conversation["id"], uuid4(), "Question")
    run, created = repo.start(1, conversation["id"], uuid4(), "Question")
    assert created
    assert repo.finish(2, run["id"], run["lease_token"], state="completed", text="Forged") is False
    assert repo.finish(1, run["id"], run["lease_token"], state="completed", text="Answer")
    assert repo.turns(1, conversation["id"])[0]["assistant_text"] == "Answer"


def test_concurrent_duplicate_generates_one_run(database):
    repo, _ = database
    conversation, submission = repo.create(1)["id"], uuid4()
    barrier = Barrier(2)

    def claim():
        barrier.wait(timeout=5)
        return repo.start(1, conversation, submission, "Same question")

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: claim(), range(2)))
    assert sum(created for _, created in results) == 1
    assert results[0][0]["id"] == results[1][0]["id"]
    with pytest.raises(AssistantConflict, match="submission_changed"):
        repo.start(1, conversation, submission, "Changed")


def test_expired_lease_reconciliation_and_stale_completion(database):
    repo, connection = database
    conversation = repo.create(1)["id"]
    old, _ = repo.start(1, conversation, uuid4(), "Old")
    with connection() as conn, conn.cursor() as cur:
        cur.execute(f"UPDATE {repo.runs} SET lease_until=clock_timestamp()-interval '1 second' WHERE id=%s", (old["id"],))
        conn.commit()
    new, created = repo.start(1, conversation, uuid4(), "New")
    assert created and new["id"] != old["id"]
    assert not repo.finish(1, old["id"], old["lease_token"], state="completed", text="Late")
    assert repo.turns(1, conversation)[0]["state"] == "interrupted"


def test_concurrent_owner_capacity_and_rollback(database):
    repo, _ = database
    conversations = [repo.create(1)["id"], repo.create(1)["id"]]
    barrier = Barrier(2)

    def claim(conversation):
        barrier.wait(timeout=5)
        try:
            return repo.start(1, conversation, uuid4(), "Question")[1]
        except AssistantConflict:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(claim, conversations)) == 1
    # Failed claim transaction doesn't leave the lock held or poison later reads.
    assert len(repo.list_conversations(1)) == 2


def test_composite_foreign_key_denies_cross_owner_message(database):
    repo, connection = database
    run, _ = repo.start(1, repo.create(1)["id"], uuid4(), "Question")
    with pytest.raises(psycopg2.IntegrityError), connection() as conn, conn.cursor() as cur:
        cur.execute(f"INSERT INTO {repo.messages}(id,run_id,conversation_id,user_id,role,content) "
                    "VALUES(%s,%s,%s,2,'assistant','Forged')", (str(uuid4()), run["id"], run["conversation_id"]))


def test_watchlist_snapshot_is_owned_primary_dated_and_bounded(database):
    repo, connection = database
    schema = os.environ["SIGNAL_DESK_SCHEMA"]
    with connection() as conn, conn.cursor() as cur:
        cur.execute(f"INSERT INTO {schema}.watchlists_test VALUES(1,1,'Primary'),(2,2,'Primary'),(3,1,'Other')")
        cur.execute(f"INSERT INTO {schema}.watchlist_tickers_test VALUES(1,'MSFT'),(1,'AAPL'),(2,'NVDA'),(3,'TSLA')")
        conn.commit()
    snapshot = repo.watchlist_snapshot(1)
    assert snapshot["tickers"] == ["AAPL", "MSFT"]
    assert snapshot["captured_at"].tzinfo is not None
    assert repo.watchlist_snapshot(2)["tickers"] == ["NVDA"]
    assert repo.watchlist_snapshot(3)["tickers"] == []
    with connection() as conn, conn.cursor() as cur:
        cur.execute(f"INSERT INTO {schema}.watchlist_tickers_test "
                    "SELECT 1,'T'||n FROM generate_series(1,49) n")
        conn.commit()
    with pytest.raises(ValueError, match="context_capacity"):
        repo.watchlist_snapshot(1)


def test_reload_recovers_only_owned_expired_runs(database):
    repo, connection = database
    conversations = [repo.create(owner)["id"] for owner in (1, 2, 3)]
    runs = [repo.start(owner, conversation, uuid4(), "Question")[0]
            for owner, conversation in zip((1, 2, 3), conversations, strict=True)]
    with connection() as conn, conn.cursor() as cur:
        cur.execute(f"UPDATE {repo.runs} SET lease_until=clock_timestamp()-interval '1 second' WHERE user_id IN (1,2)")
        conn.commit()
    assert repo.turns(1, conversations[0])[0]["state"] == "interrupted"
    with connection() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT state FROM {repo.runs} WHERE id=%s", (runs[1]["id"],))
        assert cur.fetchone()["state"] == "running"
    assert repo.reconcile_expired(limit=1) == 1
    assert repo.reconcile_expired() == 0
    assert repo.turns(3, conversations[2])[0]["state"] == "running"
    assert not repo.finish(2, runs[1]["id"], runs[1]["lease_token"], state="completed", text="Late")
