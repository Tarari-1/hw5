"""Reset the shop to the original data. Shared by POST /api/reset and the command line.

- Copies data/campus_customs.db over data/campus_customs_new.db (temp file, fsync,
  os.replace) and verifies the SHA-256 of the copy equals the original's.
- Clears the three stores (approvals, drafts board, ticket resolutions) to empty
  arrays. A store that does not exist is left absent.
- Never touches output/audit_trail.json except to APPEND one "note" entry saying a
  reset happened.

The original is only ever read. CAMPUS_CUSTOMS_ORIGINAL_DB / CAMPUS_CUSTOMS_DB /
CAMPUS_CUSTOMS_STORE_DIR / AUDIT_TRAIL_PATH point everything at scratch copies for tests.

Usage: .venv/bin/python scripts/reset_db.py --confirm
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import sys
from contextlib import closing
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend import audit  # noqa: E402
from backend.agents import MODEL_NAME  # noqa: E402  (also pins the audit model name)
from backend.models import AuditEntry  # noqa: E402
from mcp_server import stores  # noqa: E402

ORIGINAL_DB = Path(os.environ.get("CAMPUS_CUSTOMS_ORIGINAL_DB") or ROOT / "data" / "campus_customs.db").resolve()
WORKING_DB = Path(os.environ.get("CAMPUS_CUSTOMS_DB") or ROOT / "data" / "campus_customs_new.db").resolve()
STORE_NAMES = (stores.APPROVALS, stores.DRAFTS, stores.RESOLUTIONS)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def reset_database(run_label: str = "operator", source: str = "cli") -> dict[str, Any]:
    """Restore the working database from the original and clear the stores. Raises on failure."""
    if WORKING_DB == ORIGINAL_DB or WORKING_DB.name == "campus_customs.db":
        raise RuntimeError("Refusing to reset: the working database path points at the original.")
    if not ORIGINAL_DB.is_file():
        raise FileNotFoundError("Original database not found.")
    original_sha = sha256(ORIGINAL_DB)

    tmp = WORKING_DB.with_name(f"{WORKING_DB.name}.reset-tmp-{os.getpid()}")
    shutil.copyfile(ORIGINAL_DB, tmp)
    with open(tmp, "rb+") as fh:
        os.fsync(fh.fileno())
    os.replace(tmp, WORKING_DB)
    working_sha = sha256(WORKING_DB)
    if working_sha != original_sha:
        raise RuntimeError("Reset copy does not match the original checksum.")

    cleared: dict[str, Any] = {}
    for name in STORE_NAMES:
        path = stores.STORE_DIR / name
        if not path.exists():
            cleared[name] = "absent"
            continue
        with stores.locked(name) as records:
            removed = len(records)
            records.clear()
        cleared[name] = f"cleared ({removed} record(s) removed)"

    with closing(sqlite3.connect(f"{WORKING_DB.as_uri()}?mode=ro", uri=True)) as conn:
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        counts = {t: conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in tables}

    before = audit.count()
    audit.append([AuditEntry(
        ts=audit.now_iso(), run_label=run_label, run_id="reset", ticket_id=None, agent=None, depth=None,
        parent_agent=None, step="note", name="database_reset", arguments={"source": source},
        result_summary=(f"Working database restored from the original (sha256 {working_sha[:12]}...); "
                        f"stores: {json.dumps(cleared)}. Audit trail kept: {before} earlier entries."),
        model=MODEL_NAME,
    ).model_dump()])
    return {
        "ok": True,
        "original_sha256": original_sha,
        "working_sha256": working_sha,
        "checksums_match": True,
        "row_counts": counts,
        "stores": cleared,
        "audit_entries_before": before,
        "audit_entries_after": audit.count(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--confirm", action="store_true", help="required: really reset the working data")
    args = parser.parse_args()
    if not args.confirm:
        parser.error("refusing to reset without --confirm")
    print(json.dumps(reset_database(source="cli"), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
