"""Trigger incremental synchronization of the managed research AI Search index.

The filename is retained as a compatibility entry point for the Phase 3 bundle;
chunking and embedding are now owned by the Spark table and Delta Sync index.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from databricks.sdk import WorkspaceClient

runtime_file = globals().get("__file__") or globals().get("filename")
if runtime_file:
    sys.path.insert(0, str(Path(runtime_file).resolve().parents[1]))

DEFAULT_INDEX = "bootcamp_students.student_sri.signal_desk_research_chunks_index"


def run(index_name: str | None = None, workspace: WorkspaceClient | None = None) -> dict:
    selected_index = index_name or os.environ.get("SIGNAL_DESK_VECTOR_SEARCH_INDEX", DEFAULT_INDEX)
    client = workspace or WorkspaceClient()
    before = client.vector_search_indexes.get_index(index_name=selected_index)
    status = getattr(before, "status", None)
    if status is not None and getattr(status, "ready", None) is False:
        message = getattr(status, "message", None) or "unknown state"
        raise RuntimeError(f"AI Search index is not ready: {message}")
    client.vector_search_indexes.sync_index(index_name=selected_index)
    return {
        "status": "sync_requested",
        "index": selected_index,
        "prior_ready": getattr(status, "ready", None),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index-name", default=os.environ.get("SIGNAL_DESK_VECTOR_SEARCH_INDEX", DEFAULT_INDEX))
    args = parser.parse_args()
    print(json.dumps(run(args.index_name), sort_keys=True))
    return 0


if __name__ == "__main__":
    main()
