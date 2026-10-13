"""Owner-scoped PostgreSQL persistence and cross-worker generation leases.

Caller passes the authenticated application user ID, never a model/browser owner.
All transactions finish before returning; none span a Supervisor network call.
"""

from __future__ import annotations

import hashlib
from uuid import UUID, uuid4

from dashboard import lakebase


class AssistantNotFound(LookupError):
    pass


class AssistantConflict(ValueError):
    pass


def identifier(value) -> str:
    return str(UUID(str(value)))


class AssistantRepository:
    def __init__(self, connection=None, *, capacity=4):
        if not 1 <= capacity <= 20:
            raise ValueError("invalid_capacity")
        self.connection = connection or lakebase.connection
        self.capacity = capacity
        self.conversations = lakebase.table_name("assistant_conversations")
        self.runs = lakebase.table_name("assistant_runs")
        self.messages = lakebase.table_name("assistant_messages")

    def create(self, owner: int, title="Research") -> dict:
        if not isinstance(title, str) or not 1 <= len(title.strip()) <= 200:
            raise ValueError("invalid_title")
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(f"INSERT INTO {self.conversations}(id,user_id,title) VALUES(%s,%s,%s) RETURNING *",
                        (str(uuid4()), owner, title.strip()))
            result = dict(cur.fetchone())
            conn.commit()
            return result

    def watchlist_snapshot(self, owner: int) -> dict:
        watchlists = lakebase.table_name("watchlists")
        members = lakebase.table_name("watchlist_tickers")
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT t.ticker FROM {watchlists} w JOIN {members} t ON t.watchlist_id=w.id "
                        "WHERE w.user_id=%s AND w.name='Primary' ORDER BY t.ticker LIMIT 51", (owner,))
            tickers = [row["ticker"] for row in cur.fetchall()]
            cur.execute("SELECT clock_timestamp() AS captured_at")
            timestamp = cur.fetchone()["captured_at"]
            conn.commit()
            if len(tickers) > 50:
                raise ValueError("context_capacity")
            return {"tickers": tickers, "captured_at": timestamp}

    def list_conversations(self, owner: int, *, limit=20, before=None) -> list[dict]:
        if not 1 <= limit <= 100:
            raise ValueError("invalid_limit")
        with self.connection() as conn, conn.cursor() as cur:
            # Cursor is an owned conversation ID; missing/cross-owner cursors yield no rows.
            cur.execute(f"SELECT id,title,created_at FROM {self.conversations} WHERE user_id=%s "
                        f"AND (%s::uuid IS NULL OR (created_at,id)<(SELECT created_at,id FROM {self.conversations} "
                        "WHERE id=%s::uuid AND user_id=%s)) ORDER BY created_at DESC,id DESC LIMIT %s",
                        (owner, identifier(before) if before else None, identifier(before) if before else None, owner, limit))
            result = [dict(row) for row in cur.fetchall()]
            conn.commit()
            return result

    def turns(self, owner: int, conversation, *, limit=10) -> list[dict]:
        if not 1 <= limit <= 100:
            raise ValueError("invalid_limit")
        conversation = identifier(conversation)
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT id FROM {self.conversations} WHERE id=%s AND user_id=%s", (conversation, owner))
            if not cur.fetchone():
                raise AssistantNotFound()
            cur.execute(f"SELECT r.id,r.state,r.created_at,u.content AS user_text,a.content AS assistant_text "
                        f"FROM {self.runs} r JOIN {self.messages} u ON u.run_id=r.id AND u.role='user' "
                        f"AND u.user_id=r.user_id LEFT JOIN {self.messages} a ON a.run_id=r.id "
                        "AND a.role='assistant' AND a.user_id=r.user_id "
                        "WHERE r.conversation_id=%s AND r.user_id=%s ORDER BY r.created_at DESC,r.id DESC LIMIT %s",
                        (conversation, owner, limit))
            rows = [dict(row) for row in cur.fetchall()]
            conn.commit()
            return list(reversed(rows))

    def start(self, owner: int, conversation, submission, question: str) -> tuple[dict, bool]:
        conversation, submission = identifier(conversation), identifier(submission)
        if not isinstance(question, str) or not question.strip() or len(question) > 4000:
            raise ValueError("invalid_message")
        question = question.strip()
        fingerprint = hashlib.sha256(question.encode()).hexdigest()
        with self.connection() as conn, conn.cursor() as cur:
            # Serialize brief claims globally, including reconciliation and capacity count.
            # Fixed namespaced lock is transaction-local, not held across streaming.
            cur.execute("SELECT pg_advisory_xact_lock(734901, 2)")
            cur.execute(f"SELECT id FROM {self.conversations} WHERE id=%s AND user_id=%s", (conversation, owner))
            if not cur.fetchone():
                raise AssistantNotFound()
            cur.execute(f"UPDATE {self.runs} SET state='interrupted',finished_at=clock_timestamp(),error_code='lease_expired' "
                        "WHERE state='running' AND lease_until<=clock_timestamp()")
            cur.execute(f"SELECT * FROM {self.runs} WHERE conversation_id=%s AND client_message_id=%s AND user_id=%s",
                        (conversation, submission, owner))
            previous = cur.fetchone()
            if previous:
                if previous["payload_hash"] != fingerprint:
                    raise AssistantConflict("submission_changed")
                conn.commit()
                return dict(previous), False
            cur.execute(f"SELECT count(*) AS total,count(*) FILTER(WHERE user_id=%s) AS owned "
                        f"FROM {self.runs} WHERE state='running'", (owner,))
            count = cur.fetchone()
            if count["owned"] or count["total"] >= self.capacity:
                raise AssistantConflict("generation_capacity")
            run_id, lease = str(uuid4()), str(uuid4())
            cur.execute(f"INSERT INTO {self.runs}(id,conversation_id,user_id,client_message_id,payload_hash,state,lease_token,lease_until) "
                        "VALUES(%s,%s,%s,%s,%s,'running',%s,clock_timestamp()+interval '210 seconds') RETURNING *",
                        (run_id, conversation, owner, submission, fingerprint, lease))
            result = dict(cur.fetchone())
            cur.execute(f"INSERT INTO {self.messages}(id,run_id,conversation_id,user_id,role,content) "
                        "VALUES(%s,%s,%s,%s,'user',%s)", (str(uuid4()), run_id, conversation, owner, question))
            conn.commit()
            return result, True

    def finish(self, owner: int, run, lease, *, state: str, text: str, error_code=None) -> bool:
        if state not in {"completed", "failed", "interrupted"}:
            raise ValueError("invalid_state")
        if not isinstance(text, str) or len(text.encode()) > 100000:
            raise ValueError("invalid_text")
        if error_code not in {None, "dependency_error", "lease_expired", "disconnected", "invalid_stream"}:
            raise ValueError("invalid_error_code")
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {self.runs} SET state=%s,finished_at=clock_timestamp(),error_code=%s "
                        "WHERE id=%s AND user_id=%s AND lease_token=%s AND state='running' "
                        "AND lease_until>clock_timestamp() RETURNING conversation_id",
                        (state, error_code, identifier(run), owner, identifier(lease)))
            result = cur.fetchone()
            if not result:
                conn.commit()
                return False
            cur.execute(f"INSERT INTO {self.messages}(id,run_id,conversation_id,user_id,role,content) "
                        "VALUES(%s,%s,%s,%s,'assistant',%s)",
                        (str(uuid4()), identifier(run), result["conversation_id"], owner, text))
            conn.commit()
            return True
