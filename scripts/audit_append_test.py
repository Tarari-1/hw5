"""Append test for output/audit_trail.json: two real (cheap) runs, count must only grow.

Each run is one Facilities call ("state your role and list your tools") through
Portkey, MCP pointed at a scratch database. Also checks that the entries already
in the file are left byte-for-byte unchanged (true append), and that a corrupt
audit file is renamed aside, never deleted (on a scratch path, no model call).

Usage: .venv/bin/python scripts/audit_append_test.py <scratch_db> <scratch_store_dir>
"""

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend import audit  # noqa: E402
from backend.agents import run_team  # noqa: E402


def snapshot() -> list:
    return json.loads(audit.AUDIT_TRAIL_PATH.read_text(encoding="utf-8"))


async def main(db: Path, store: Path) -> int:
    before = snapshot()
    print(f"run 0 (before): {len(before)} entries")
    prev = before
    for i in (1, 2):
        out = await run_team("State your role and list your tools.", run_label="problem-5-wiring-test",
                             start_agent="facilities", db_path=db, store_dir=store)
        now = snapshot()
        print(f"run {i}: status={out.status} run_id={out.run_id} -> {len(now)} entries "
              f"(+{len(now) - len(prev)}), earlier entries unchanged: {now[:len(prev)] == prev}")
        assert len(now) > len(prev) and now[:len(prev)] == prev
        prev = now
    labels = {e["run_label"] for e in prev}
    print(f"run_label values in file: {sorted(labels)}")

    # Corrupt-file handling on a scratch path (no model call).
    tmpdir = Path(tempfile.mkdtemp())
    audit.AUDIT_TRAIL_PATH = tmpdir / "audit_trail.json"
    audit.AUDIT_TRAIL_PATH.write_text("[{not valid json")
    audit.append([{"run_label": "problem-5-wiring-test", "step": "error", "note": "corrupt-file test"}])
    print(f"corrupt test files: {sorted(p.name for p in tmpdir.iterdir() if not p.name.endswith('.lock'))}; "
          f"new file valid with {len(json.loads(audit.AUDIT_TRAIL_PATH.read_text()))} entry")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(Path(sys.argv[1]), Path(sys.argv[2]))))
