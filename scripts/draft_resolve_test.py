"""save_customer_draft and resolve_ticket tests through the real MCP server, on a
scratch copy of the database and scratch stores only.

Usage: .venv/bin/python scripts/draft_resolve_test.py <scratch_dir>
"""

import asyncio
import json
import os
import shutil
import sqlite3
import sys
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import PythonStdioTransport

ROOT = Path(__file__).resolve().parents[1]
WORKING = ROOT / "data" / "campus_customs_new.db"


def tickets(db: Path, title: str) -> None:
    conn = sqlite3.connect(f"{db.as_uri()}?mode=ro", uri=True)
    rows = conn.execute("SELECT id, type, status FROM tickets ORDER BY id").fetchall()
    conn.close()
    print(f"\n----- scratch tickets {title}: {rows}")


def store(path: Path) -> None:
    print(f"{path.name}: {path.read_text() if path.exists() else 'does not exist'}")


async def main(scratch: Path) -> int:
    if scratch.exists():
        shutil.rmtree(scratch)
    (scratch / "store").mkdir(parents=True)
    db, st = scratch / "scratch.db", scratch / "store"
    shutil.copyfile(WORKING, db)
    print(f"scratch db: {db}\nscratch store dir: {st}")
    tickets(db, "BEFORE")
    store(st / "drafts_board.json")
    store(st / "ticket_resolutions.json")

    transport = PythonStdioTransport(ROOT / "mcp_server" / "server.py", python_cmd=sys.executable, keep_alive=False,
                                     env={"PATH": os.environ["PATH"], "CAMPUS_CUSTOMS_DB": str(db),
                                          "CAMPUS_CUSTOMS_STORE_DIR": str(st), "FASTMCP_LOG_LEVEL": "WARNING"})
    async with Client(transport) as client:
        async def call(label, tool, **args):
            res = await client.call_tool(tool, args)
            print(f"\n[{label}] {tool}({json.dumps(args)})\n  -> {json.dumps(res.data)}")

        await call("1", "save_customer_draft", ticket_id=101, recipient="Tauhid Zaman",
                   subject="Your Classic Bulldog Tee (size S)",
                   body="Hi Tauhid, thanks for your order. Size S is out of stock right now; M, L and XL are "
                        "available. We'll follow up with restock timing. (SCRATCH TEST DRAFT)")
        await call("2", "save_customer_draft", ticket_id=999, recipient="Nobody", subject="x", body="x")
        await call("3", "resolve_ticket", ticket_id=102, status="resolved",
                   resolution_note="SCRATCH TEST: rent payment proposed for human approval.")
        await call("4", "resolve_ticket", ticket_id=999, status="resolved", resolution_note="unknown ticket test")
        await call("5", "resolve_ticket", ticket_id=102, status="resolved", resolution_note="second attempt")
        await call("6", "resolve_ticket", ticket_id=103, status="closed", resolution_note="bad status test")
        await call("7", "get_ticket", ticket_id=102)

    tickets(db, "AFTER")
    store(st / "drafts_board.json")
    store(st / "ticket_resolutions.json")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(Path(sys.argv[1]))))
