"""Human approval CLI for agent proposals (payments and purchase orders).

Usage:
  .venv/bin/python scripts/approve.py list
  .venv/bin/python scripts/approve.py approve PAY-0001 --by "Jane Doe"
  .venv/bin/python scripts/approve.py reject  PAY-0001 --by "Jane Doe"

Run by a person at a terminal. Agents cannot reach this script: it is not an MCP
tool. Set CAMPUS_CUSTOMS_STORE_DIR to point at a scratch store when testing.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.approvals import decide, pending  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", choices=["list", "approve", "reject"])
    parser.add_argument("proposal_id", nargs="?")
    parser.add_argument("--by", help="name of the human approving or rejecting")
    args = parser.parse_args()
    if args.action == "list":
        print(json.dumps(pending(), indent=2))
        return 0
    if not args.proposal_id or not args.by:
        parser.error("approve/reject need a proposal_id and --by NAME")
    result = decide(args.proposal_id, args.by, approve=args.action == "approve")
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
