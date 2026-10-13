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
