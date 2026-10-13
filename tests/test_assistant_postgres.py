"""Opt-in integration against disposable local PostgreSQL, never Lakebase."""

import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import psycopg2
import pytest
from psycopg2.extras import RealDictCursor

from dashboard.assistant_repository import AssistantConflict, AssistantNotFound, AssistantRepository
from dashboard.assistant_service import AssistantService
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
        cur.execute(f"INSERT INTO {schema}.users_test VALUES(1),(2),(3),(4),(5)")
        # Minimal existing watchlist tables, matching their production keys.
        cur.execute(f"CREATE TABLE {schema}.watchlists_test(id BIGINT PRIMARY KEY, "
                    f"user_id BIGINT REFERENCES {schema}.users_test(id), name TEXT, UNIQUE(user_id,name))")
        cur.execute(f"CREATE TABLE {schema}.watchlist_tickers_test(watchlist_id BIGINT "
                    f"REFERENCES {schema}.watchlists_test(id), ticker TEXT, PRIMARY KEY(watchlist_id,ticker))")
        sql = render_migration((Path(__file__).parents[1] / "mcp_server/migrations/0006_assistant_conversations.sql").read_text())
        cur.execute(sql)
        cur.execute(sql)  # Repeatable additive DDL.
        sql = render_migration((Path(__file__).parents[1] / "mcp_server/migrations/0007_assistant_retention.sql").read_text())
        cur.execute(sql)
        cur.execute(sql)
        sql = render_migration((Path(__file__).parents[1] / "mcp_server/migrations/0008_assistant_proposals.sql").read_text())
        cur.execute(sql)
        cur.execute(sql)
        sql = render_migration((Path(__file__).parents[1] / "mcp_server/migrations/0009_assistant_execution.sql").read_text())
        cur.execute(sql)
        cur.execute(sql)

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


def test_retention_preview_redaction_and_duplicate_safety(database):
    repo, connection = database
    conversation, submission = repo.create(1, title="Private old title")["id"], uuid4()
    old, _ = repo.start(1, conversation, submission, "Old private question")
    assert repo.finish(1, old["id"], old["lease_token"], state="completed", text="Old private answer")
    fresh, _ = repo.start(2, repo.create(2)["id"], uuid4(), "Fresh")
    repo.finish(2, fresh["id"], fresh["lease_token"], state="completed", text="Fresh answer")
    live, _ = repo.start(3, repo.create(3)["id"], uuid4(), "Active")
    with connection() as conn, conn.cursor() as cur:
        cur.execute(f"UPDATE {repo.runs} SET finished_at=clock_timestamp()-interval '31 days' WHERE id=%s", (old["id"],))
        cur.execute(f"UPDATE {repo.conversations} SET created_at=clock_timestamp()-interval '31 days' WHERE id=%s", (conversation,))
        # Aged messages alone never authorize redaction of a recent/live run.
        cur.execute(f"UPDATE {repo.messages} SET created_at=clock_timestamp()-interval '40 days'")
        conn.commit()
    assert repo.redact_expired_transcripts() == 2
    assert repo.turns(1, conversation)[0]["user_text"] == "Old private question"
    assert repo.redact_expired_transcripts(apply=True, limit=1) == 1
    assert repo.redact_expired_transcripts(apply=True) == 1
    assert repo.redact_expired_transcripts(apply=True) == 0
    turn = repo.turns(1, conversation)[0]
    assert turn["user_text"] == turn["assistant_text"] == ""
    assert turn["user_redacted_at"] is not None and turn["assistant_redacted_at"] is not None
    assert repo.list_conversations(1)[0]["title"] == "Research"
    duplicate, created = repo.start(1, conversation, submission, "Old private question")
    assert not created and duplicate["id"] == old["id"]
    assert repo.turns(2, fresh["conversation_id"])[0]["assistant_text"] == "Fresh answer"
    assert repo.turns(3, live["conversation_id"])[0]["user_text"] == "Active"


def test_four_concurrent_generations_release_database_connections(database):
    import threading
    import time

    repo, connection = database
    from psycopg2.pool import ThreadedConnectionPool

    connection_pool = ThreadedConnectionPool(1, 5, host="127.0.0.1",
        port=int(os.environ["ASSISTANT_TEST_POSTGRES_PORT"]), dbname="postgres", user="postgres",
        cursor_factory=RealDictCursor)
    active = threading.local()
    maximum = [0]
    current = [0]
    lock = threading.Lock()

    @contextmanager
    def tracked_connection():
        conn = connection_pool.getconn()
        active.connections = getattr(active, "connections", 0) + 1
        with lock:
            current[0] += 1
            maximum[0] = max(maximum[0], current[0])
        try:
            yield conn
        except BaseException:
            conn.rollback()
            raise
        finally:
            active.connections -= 1
            with lock:
                current[0] -= 1
            connection_pool.putconn(conn)

    repo = AssistantRepository(tracked_connection)
    barrier = Barrier(4)
    ready = threading.Event()
    release = threading.Event()
    conversations = [repo.create(owner)["id"] for owner in range(1, 6)]

    class Client:
        def stream(self, history, state):
            assert getattr(active, "connections", 0) == 0
            barrier.wait(timeout=5)
            ready.set()
            assert release.wait(5)
            state.final_text = "Answer"
            state.finalized = state.terminal = True
            yield "Answer"

    service = AssistantService(repo, Client())
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(lambda owner=owner: list(service.generate(
            owner, conversations[owner-1], uuid4(), "Question"))) for owner in range(1, 5)]
        try:
            assert ready.wait(5)
            with lock:
                assert current[0] == 0
            with pytest.raises(AssistantConflict, match="generation_capacity"):
                repo.start(5, conversations[4], uuid4(), "Over capacity")
        finally:
            release.set()
        assert all(f.result(timeout=5)[-1]["type"] == "complete" for f in futures)
    assert current[0] == 0 and maximum[0] <= 4
    connection_pool.closeall()
    print(f"local_capacity=4 max_db_connections={maximum[0]} total_seconds={time.monotonic()-started:.3f}")


def test_abrupt_worker_process_death_recovers_without_regeneration(database):
    repo, connection = database
    conversation, submission = repo.create(1)["id"], uuid4()
    # Child connects ONLY to the explicit disposable localhost fixture.
    script = """
import os, sys
from contextlib import contextmanager
import psycopg2
from psycopg2.extras import RealDictCursor
from dashboard.assistant_repository import AssistantRepository
@contextmanager
def connection():
    conn = psycopg2.connect(host='127.0.0.1', port=int(os.environ['ASSISTANT_TEST_POSTGRES_PORT']),
                           dbname='postgres', user='postgres', cursor_factory=RealDictCursor)
    try:
        yield conn
    finally:
        conn.close()
AssistantRepository(connection).start(1, sys.argv[1], sys.argv[2], 'Crash question')
os._exit(23)
"""
    process = subprocess.run([sys.executable, "-c", script, str(conversation), str(submission)],
                             capture_output=True, timeout=10, check=False)
    assert process.returncode == 23
    assert repo.turns(1, conversation)[0]["state"] == "running"
    with connection() as conn, conn.cursor() as cur:
        cur.execute(f"UPDATE {repo.runs} SET lease_until=clock_timestamp()-interval '1 second' WHERE conversation_id=%s",
                    (conversation,))
        conn.commit()
    assert repo.reconcile_expired() == 1
    run, created = repo.start(1, conversation, submission, "Crash question")
    assert not created and run["state"] == "interrupted"


def test_lost_commit_acknowledgement_returns_error_but_duplicate_finds_saved_run(database):
    repo, connection = database
    conversation, submission = repo.create(1)["id"], uuid4()

    class LostAcknowledgement:
        def __init__(self, conn):
            self.conn = conn

        def cursor(self):
            return self.conn.cursor()

        def commit(self):
            self.conn.commit()
            raise RuntimeError("private-driver-details")

    @contextmanager
    def uncertain_connection():
        with connection() as conn:
            yield LostAcknowledgement(conn)

    repo.finish = AssistantRepository(uncertain_connection).finish

    class Client:
        def stream(self, history, state):
            state.final_text = "Answer"
            state.finalized = state.terminal = True
            yield "Answer"

    events = list(AssistantService(repo, Client()).generate(1, conversation, submission, "Question"))
    assert events[-1]["error_code"] == "storage_unavailable"
    assert "private-driver" not in str(events)
    saved, created = repo.start(1, conversation, submission, "Question")
    assert not created and saved["state"] == "completed"
    assert repo.turns(1, conversation)[0]["assistant_text"] == "Answer"


def test_proposal_revision_dismissal_expiry_and_completed_origin(database):
    from dashboard.assistant_proposals import ProposalRepository

    repo, connection = database
    proposals = ProposalRepository(connection)
    conversation = repo.create(1)["id"]
    run, _ = repo.start(1, conversation, uuid4(), "Draft only")
    payload = {"schema_version":"1", "type":"watchlist_add", "arguments":{"ticker":"AAPL"}}
    with pytest.raises(AssistantNotFound):
        proposals.create(1, run["id"], payload)
    repo.finish(1, run["id"], run["lease_token"], state="completed", text="Draft prepared")
    draft = proposals.create(1, run["id"], payload)
    assert proposals.create(1, run["id"], payload)["id"] == draft["id"]
    with pytest.raises(AssistantNotFound):
        proposals.review(2, draft["id"], draft["payload_hash"])
    revised = proposals.revise(1, draft["id"], draft["payload_hash"], {"ticker":"MSFT"})
    assert revised["idempotency_key"] != draft["idempotency_key"] and revised["revision"] == 2
    with pytest.raises(AssistantConflict):
        proposals.review(1, draft["id"], draft["payload_hash"])
    reverted = proposals.revise(1, revised["id"], revised["payload_hash"], {"ticker":"AAPL"})
    assert reverted["idempotency_key"] != draft["idempotency_key"]
    assert proposals.dismiss(1, reverted["id"], reverted["payload_hash"])["state"] == "dismissed"
    another = proposals.create(1, run["id"], {**payload, "arguments":{"ticker":"NVDA"}})
    with connection() as conn, conn.cursor() as cur:
        cur.execute(f"UPDATE {proposals.table} SET expires_at=clock_timestamp()-interval '1 second' WHERE id=%s", (another["id"],))
        conn.commit()
    assert any(row["state"] == "expired" for row in proposals.list(1, conversation))
    with pytest.raises(AssistantConflict):
        proposals.review(1, another["id"], another["payload_hash"])


def test_concurrent_proposal_claims_once_without_changing_key(database):
    from dashboard.assistant_proposals import ProposalRepository

    repo, connection = database
    proposals = ProposalRepository(connection)
    run, _ = repo.start(1, repo.create(1)["id"], uuid4(), "Draft")
    repo.finish(1, run["id"], run["lease_token"], state="completed", text="Draft ready")
    draft = proposals.create(1, run["id"], {"type":"watchlist_add", "arguments":{"ticker":"AAPL"}})
    barrier = Barrier(2)

    def claim():
        barrier.wait(timeout=5)
        try:
            return proposals.claim(1, draft["id"], draft["payload_hash"])
        except AssistantConflict:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: claim(), range(2)))
    claimed = [row for row in results if row]
    assert len(claimed) == 1 and claimed[0]["idempotency_key"] == draft["idempotency_key"]


def test_execution_recovery_preserves_key_and_rejects_stale_owner(database):
    from dashboard.assistant_proposals import ProposalRepository

    repo, connection = database
    proposals = ProposalRepository(connection)
    run, _ = repo.start(1, repo.create(1)["id"], uuid4(), "Confirm draft")
    repo.finish(1, run["id"], run["lease_token"], state="completed", text="Draft")
    draft = proposals.create(1, run["id"], {"type":"watchlist_add", "arguments":{"ticker":"AAPL"}})
    old, claimed = proposals.begin_execution(1, draft["id"], draft["payload_hash"])
    assert claimed
    assert proposals.begin_execution(1, draft["id"], draft["payload_hash"])[1] is False
    with pytest.raises(AssistantNotFound):
        proposals.begin_execution(2, draft["id"], draft["payload_hash"])
    with pytest.raises(AssistantConflict):
        proposals.begin_execution(1, draft["id"], "a"*64)
    with connection() as conn, conn.cursor() as cur:
        cur.execute(f"UPDATE {proposals.table} SET lease_until=clock_timestamp()-interval '1 second',"
                    "expires_at=clock_timestamp()-interval '1 second' WHERE id=%s", (draft["id"],))
        conn.commit()
    recovered, claimed = proposals.begin_execution(1, draft["id"], draft["payload_hash"])
    assert claimed and recovered["idempotency_key"] == old["idempotency_key"]
    assert recovered["lease_token"] != old["lease_token"]
    assert not proposals.finish_execution(1, old["id"], old["lease_token"], state="succeeded")
    receipt = {"status":"success", "ticker":"AAPL", "verification":"verified"}
    assert proposals.finish_execution(1, recovered["id"], recovered["lease_token"], state="succeeded", receipt=receipt)
    saved, claimed = proposals.begin_execution(1, draft["id"], draft["payload_hash"])
    assert not claimed and saved["receipt"] == receipt


def test_lost_business_reply_recovers_one_note_with_owner_readback(database):
    from psycopg2.extras import Json

    from dashboard.assistant_execution import ExecutionService
    from dashboard.assistant_proposals import ProposalRepository
    from dashboard.user_writes import UserWrites

    repo, connection = database
    proposals = ProposalRepository(connection)
    notes = os.environ["SIGNAL_DESK_SCHEMA"] + ".research_notes_test"
    with connection() as conn, conn.cursor() as cur:
        cur.execute(f"CREATE TABLE {notes}(id BIGINT PRIMARY KEY,user_id BIGINT,ticker TEXT,title TEXT,note_text TEXT,thesis_tags JSONB)")
        conn.commit()
    run, _ = repo.start(1, repo.create(1)["id"], uuid4(), "Save note")
    repo.finish(1, run["id"], run["lease_token"], state="completed", text="Draft")
    payload = {"type":"save_note", "arguments":{"ticker":"AAPL","title":"Thesis","note_text":"Exact body","thesis_tags":[]}}
    draft = proposals.create(1, run["id"], payload)
    committed = set()
    tokens = []

    class Client:
        def save_research_note(self, **kwargs):
            tokens.append(kwargs["access_token"])
            key = kwargs["idempotency_key"]
            if key not in committed:
                with connection() as conn, conn.cursor() as cur:
                    cur.execute(f"INSERT INTO {notes} VALUES(42,1,%s,%s,%s,%s)",
                                (kwargs["ticker"],kwargs["title"],kwargs["note_text"],Json(kwargs["thesis_tags"])))
                    conn.commit()
                committed.add(key)
                raise RuntimeError("reply lost after commit")
            return {"status":"success", "note_id":42}

    service = ExecutionService(proposals, UserWrites(Client(), lambda: str(uuid4()), "request"))
    assert service.execute(1,draft["id"],draft["payload_hash"])["state"] == "outcome_unknown"
    recovered = service.execute(1,draft["id"],draft["payload_hash"])
    assert recovered["state"] == "succeeded" and recovered["receipt"]["verification"] == "verified"
    assert len(committed) == 1 and len(tokens) == 2 and tokens[0] != tokens[1]
    assert not proposals.readback_saved(2,draft["payload"],recovered["receipt"])
    assert proposals.receipt_context(2,run["conversation_id"]) == []
    assert proposals.receipt_context(1,run["conversation_id"])[0]["action"] == "save_note"
    assert service.execute(1,draft["id"],draft["payload_hash"])["replayed"]
    assert len(tokens) == 2  # Third confirmation reads the saved receipt only.
