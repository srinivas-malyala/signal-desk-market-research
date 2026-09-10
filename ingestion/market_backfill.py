"""Phase 0 job entry point for the market-wide backfill.

Phase 1 replaces this capability gate with checkpointed landing logic. Keeping
the entry point executable in Phase 0 lets the bundle validate without making
uncontrolled external API requests.
"""

from __future__ import annotations

import argparse


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--schema", required=True)
    parser.add_argument("--volume", required=True)
    parser.parse_args()
    print("Phase 0 bundle smoke check passed; grouped-market ingestion is implemented in Phase 1.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
