"""Cheap live checks through Portkey (problem-5 wiring test, no ticket resolution).

  roles      one minimal call per agent: "state your role and list your tools"
  delegate   Boss asks Inventory for the stock of CC-TEE-WHITE size S

The MCP server is pointed at a scratch database copy and scratch store, so the
working copy cannot change. Audit entries are labelled problem-5-wiring-test.

Usage: .venv/bin/python scripts/live_check.py roles|delegate <scratch_db> <scratch_store_dir>
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend import audit  # noqa: E402
from backend.agents import AGENT_NAMES, MODEL_NAME, run_team  # noqa: E402

LABEL = "problem-5-wiring-test"
ROLE_PROMPT = "State your role and list your tools."
DELEGATE_PROMPT = "ask Inventory to report the stock of CC-TEE-WHITE in size S"


async def main(mode: str, db: Path, store: Path) -> int:
    print(f"model: {MODEL_NAME}")
    if mode == "roles":
        for name in AGENT_NAMES:
            out = await run_team(ROLE_PROMPT, run_label=LABEL, start_agent=name, db_path=db, store_dir=store)
            print(f"\n=== {name} ===")
            print(json.dumps(out.model_dump(), indent=2))
    else:
        out = await run_team(DELEGATE_PROMPT, run_label=LABEL, start_agent="boss", db_path=db, store_dir=store)
        print(json.dumps(out.model_dump(), indent=2))
        entries = [e for e in json.loads(audit.AUDIT_TRAIL_PATH.read_text()) if e["run_id"] == out.run_id]
        print(f"\n--- {len(entries)} audit entries for run_id {out.run_id} ---")
        print(json.dumps(entries, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3]))))
