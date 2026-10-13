"""Confirmed user-bound execution; no model/browser-supplied action arguments."""

from dashboard.user_writes import WritePreparationError


class ExecutionService:
    def __init__(self, repository, writes):
        self.repository = repository
        self.writes = writes

    def execute(self, owner, proposal, digest):
        row, claimed = self.repository.begin_execution(owner, proposal, digest)
        if not claimed:
            if row["state"] == "succeeded" and (row.get("receipt") or {}).get("verification") == "pending":
                receipt = dict(row["receipt"])
                if self.verify(owner, row["payload"], receipt):
                    receipt["verification"] = "verified"
                    try:
                        self.repository.update_verification(owner, proposal, digest, receipt)
                        row["receipt"] = receipt
                    except Exception:
                        pass
            return {"state": row["state"], "receipt": row.get("receipt"), "replayed": True}
        payload, key = row["payload"], row["idempotency_key"]
        kind, args = payload["type"], payload["arguments"]
        state, receipt, error = "outcome_unknown", None, "write_uncertain"
        try:
            if kind in {"watchlist_add", "watchlist_remove"}:
                arguments = {"ticker":args["ticker"], "action":"add" if kind == "watchlist_add" else "remove"}
                result = self.writes.invoke("update_watchlist", idempotency_key=key, **arguments)
                if result.get("status") != "success" or any(result.get(k) != v for k,v in arguments.items()):
                    raise ValueError("invalid_receipt")
                receipt = {"status":"success", **arguments, "verification":"pending"}
            else:
                method = "save_research_note" if kind == "save_note" else "save_analysis_report"
                arguments = dict(args)
                if kind == "save_report":
                    arguments["source_context"] = {"origin":"assistant", "proposal_id":str(row["id"]), "payload_hash":digest}
                result = self.writes.invoke(method, idempotency_key=key, **arguments)
                id_field = "note_id" if kind == "save_note" else "report_id"
                item_id = result.get(id_field)
                if result.get("status") != "success" or type(item_id) is not int or item_id <= 0:
                    raise ValueError("invalid_receipt")
                receipt = {"status":"success", id_field:item_id, "verification":"pending"}
            state, error = "succeeded", None
            if self.verify(owner, payload, receipt):
                receipt["verification"] = "verified"
        except WritePreparationError:
            state, error = "failed", "preparation_failed"
        except Exception:
            pass  # Could have committed; only original-key recovery is safe.
        try:
            persisted = self.repository.finish_execution(owner, row["id"], row["lease_token"],
                state=state, receipt=receipt, error=error)
        except Exception:
            persisted = False
        if not persisted:
            return {"state":"outcome_unknown", "receipt":None, "error_code":"persistence_uncertain"}
        return {"state":state, "receipt":receipt, "error_code":error}

    def verify(self, owner, payload, receipt):
        try:
            kind, args = payload["type"], payload["arguments"]
            if kind in {"watchlist_add", "watchlist_remove"}:
                snapshot = self.writes.read_watchlist()
                values = snapshot["tickers"]
                if snapshot.get("status") != "success" or not isinstance(values, list):
                    return False
                tickers = {v if isinstance(v,str) else v["ticker"] for v in values}
                return (args["ticker"] in tickers) == (kind == "watchlist_add")
            return self.repository.readback_saved(owner, payload, receipt)
        except Exception:
            return False
