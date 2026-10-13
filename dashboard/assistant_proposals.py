"""Strict immutable proposal lifecycle. No business-write execution."""

import hashlib
import json
from uuid import uuid4

from psycopg2.extras import Json
from pydantic import TypeAdapter

from dashboard import lakebase
from dashboard.assistant_repository import AssistantConflict, AssistantNotFound, identifier
from shared.contracts.assistant import Proposal

ADAPTER = TypeAdapter(Proposal)


def normalize(value):
    payload = ADAPTER.validate_python(value).model_dump(mode="json")
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    if len(encoded.encode()) > 450000:
        raise ValueError("proposal_limit")
    return payload, hashlib.sha256(encoded.encode()).hexdigest()


class ProposalRepository:
    def __init__(self, connection=None):
        self.connection = connection or lakebase.connection
        self.table = lakebase.table_name("assistant_action_proposals")
        self.runs = lakebase.table_name("assistant_runs")
        self.messages = lakebase.table_name("assistant_messages")
        self.conversations = lakebase.table_name("assistant_conversations")

    def _expire(self, cur, owner):
        cur.execute(f"UPDATE {self.table} SET state='expired' WHERE user_id=%s AND state='pending' "
                    "AND expires_at<=clock_timestamp()", (owner,))

    def create(self, owner, run, candidate):
        payload, digest = normalize(candidate)
        with self.connection() as conn, conn.cursor() as cur:
            # Completed response and an owned persisted assistant message required.
            cur.execute(f"SELECT r.conversation_id,m.id AS message_id FROM {self.runs} r "
                        f"JOIN {self.messages} m ON m.run_id=r.id AND m.user_id=r.user_id AND m.role='assistant' "
                        "WHERE r.id=%s AND r.user_id=%s AND r.state='completed' AND m.redacted_at IS NULL",
                        (identifier(run), owner))
            origin = cur.fetchone()
            if not origin:
                raise AssistantNotFound()
            cur.execute(f"INSERT INTO {self.table}(id,user_id,run_id,conversation_id,origin_message_id,payload,payload_hash,"
                        "idempotency_key,state,expires_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,'pending',"
                        "clock_timestamp()+interval '30 minutes') ON CONFLICT(run_id,payload_hash) WHERE parent_id IS NULL DO NOTHING",
                        (str(uuid4()), owner, identifier(run), origin["conversation_id"], origin["message_id"],
                         Json(payload), digest, "assistant-"+str(uuid4())))
            self._expire(cur, owner)
            cur.execute(f"SELECT * FROM {self.table} WHERE user_id=%s AND run_id=%s AND payload_hash=%s AND parent_id IS NULL",
                        (owner, identifier(run), digest))
            row = dict(cur.fetchone())
            conn.commit()
            return row

    def list(self, owner, conversation):
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT id FROM {self.conversations} WHERE id=%s AND user_id=%s", (identifier(conversation), owner))
            if not cur.fetchone():
                raise AssistantNotFound()
            self._expire(cur, owner)
            cur.execute(f"SELECT * FROM {self.table} WHERE conversation_id=%s AND user_id=%s "
                        "ORDER BY created_at DESC,id DESC LIMIT 50", (identifier(conversation), owner))
            rows = [dict(row) for row in cur.fetchall()]
            conn.commit()
            return rows

    def _load(self, cur, owner, proposal, digest):
        self._expire(cur, owner)
        cur.execute(f"SELECT * FROM {self.table} WHERE id=%s AND user_id=%s FOR UPDATE", (identifier(proposal), owner))
        row = cur.fetchone()
        if not row:
            raise AssistantNotFound()
        cur.execute("SELECT clock_timestamp() AS now")
        expired = row["expires_at"] <= cur.fetchone()["now"]
        if row["payload_hash"] != digest or row["state"] != "pending" or expired:
            raise AssistantConflict("proposal_changed")
        return row

    def dismiss(self, owner, proposal, digest):
        with self.connection() as conn, conn.cursor() as cur:
            self._load(cur, owner, proposal, digest)
            cur.execute(f"UPDATE {self.table} SET state='dismissed' WHERE id=%s AND user_id=%s RETURNING *",
                        (identifier(proposal), owner))
            row = dict(cur.fetchone())
            conn.commit()
            return row

    def review(self, owner, proposal, digest):
        with self.connection() as conn, conn.cursor() as cur:
            row = dict(self._load(cur, owner, proposal, digest))
            conn.commit()
            return row

    def claim(self, owner, proposal, digest):
        """M5 preparation only: short owned claim, no network or business write.

        No route calls this until user-bound execution/recovery exists. Expired
        execution leases must NOT be blindly re-claimed after an uncertain write.
        """
        with self.connection() as conn, conn.cursor() as cur:
            self._load(cur, owner, proposal, digest)
            cur.execute(f"UPDATE {self.table} SET state='executing',lease_token=%s,"
                        "lease_until=clock_timestamp()+interval '120 seconds' WHERE id=%s AND user_id=%s "
                        "AND state='pending' AND expires_at>clock_timestamp() RETURNING *",
                        (str(uuid4()), identifier(proposal), owner))
            row = cur.fetchone()
            if not row:
                raise AssistantConflict("proposal_changed")
            conn.commit()
            return dict(row)

    def revise(self, owner, proposal, digest, arguments):
        with self.connection() as conn, conn.cursor() as cur:
            row = self._load(cur, owner, proposal, digest)
            payload, new_digest = normalize({**row["payload"], "arguments": arguments})
            if new_digest == digest:
                raise AssistantConflict("proposal_unchanged")
            cur.execute(f"UPDATE {self.table} SET state='superseded' WHERE id=%s AND user_id=%s", (identifier(proposal), owner))
            cur.execute(f"INSERT INTO {self.table}(id,user_id,run_id,conversation_id,origin_message_id,payload,payload_hash,"
                        "idempotency_key,state,expires_at,revision,parent_id) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,'pending',"
                        "clock_timestamp()+interval '30 minutes',%s,%s) RETURNING *",
                        (str(uuid4()), owner, row["run_id"], row["conversation_id"], row["origin_message_id"], Json(payload),
                         new_digest, "assistant-"+str(uuid4()), row["revision"]+1, row["id"]))
            revised = dict(cur.fetchone())
            conn.commit()
            return revised

    def begin_execution(self, owner, proposal, digest):
        """Fresh authenticated confirmation required by caller, including recovery."""
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute("SET LOCAL lock_timeout = '5s'")
            cur.execute(f"SELECT * FROM {self.table} WHERE id=%s AND user_id=%s FOR UPDATE", (identifier(proposal), owner))
            row = cur.fetchone()
            if not row:
                raise AssistantNotFound()
            _, actual_hash = normalize(row["payload"])
            if row["payload_hash"] != digest or actual_hash != digest:
                raise AssistantConflict("proposal_changed")
            cur.execute("SELECT clock_timestamp() AS now")
            now = cur.fetchone()["now"]
            if row["state"] == "succeeded" or (row["state"] == "executing" and row["lease_until"] > now):
                conn.commit()
                return dict(row), False
            recovery = row["state"] in {"outcome_unknown", "executing"}
            if not recovery and (row["state"] not in {"pending", "failed"} or row["expires_at"] <= now):
                raise AssistantConflict("proposal_changed")
            if row["state"] == "failed" and row["execution_error"] != "preparation_failed":
                raise AssistantConflict("proposal_changed")
            cur.execute(f"UPDATE {self.table} SET state='executing',lease_token=%s,"
                        "lease_until=clock_timestamp()+interval '180 seconds',execution_error=NULL "
                        "WHERE id=%s AND user_id=%s RETURNING *", (str(uuid4()), identifier(proposal), owner))
            claimed = dict(cur.fetchone())
            conn.commit()
            return claimed, True

    def finish_execution(self, owner, proposal, lease, *, state, receipt=None, error=None):
        if state not in {"succeeded", "failed", "outcome_unknown"} or error not in {None, "preparation_failed", "write_uncertain"}:
            raise ValueError("invalid_execution_state")
        if receipt is not None and len(json.dumps(receipt).encode()) > 4096:
            raise ValueError("receipt_limit")
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {self.table} SET state=%s,receipt=%s,execution_error=%s,finished_at=clock_timestamp() "
                        "WHERE id=%s AND user_id=%s AND lease_token=%s AND state='executing' "
                        "AND lease_until>clock_timestamp() RETURNING id",
                        (state, Json(receipt) if receipt is not None else None, error, identifier(proposal), owner, identifier(lease)))
            saved = cur.fetchone() is not None
            conn.commit()
            return saved

    def readback_saved(self, owner, payload, receipt):
        action, args = payload["type"], payload["arguments"]
        base = "research_notes" if action == "save_note" else "analysis_reports"
        item_id = receipt["note_id" if action == "save_note" else "report_id"]
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT * FROM {lakebase.table_name(base)} WHERE id=%s AND user_id=%s", (item_id, owner))
            row = cur.fetchone()
            conn.commit()
            return bool(row) and all(row[key] == value for key, value in args.items())

    def update_verification(self, owner, proposal, digest, receipt):
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(f"UPDATE {self.table} SET receipt=%s WHERE id=%s AND user_id=%s "
                        "AND payload_hash=%s AND state='succeeded'", (Json(receipt), identifier(proposal), owner, digest))
            conn.commit()

    def receipt_context(self, owner, conversation):
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT payload->>'type' AS action,receipt FROM {self.table} "
                        "WHERE user_id=%s AND conversation_id=%s AND state='succeeded' AND receipt IS NOT NULL "
                        "ORDER BY finished_at DESC LIMIT 3", (owner, identifier(conversation)))
            rows = [dict(row) for row in cur.fetchall()]
            conn.commit()
            # Payload text, user IDs and private keys are excluded from context.
            return rows


def public_proposal(row):
    # Execution keys and origin internals never become browser authorization.
    result = {key: row[key] for key in ("id", "payload", "payload_hash", "state", "revision", "expires_at")}
    result["receipt"] = row.get("receipt")
    return result
