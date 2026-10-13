"""Write-tool tests through the real MCP server, on a scratch copy of the database.

Copies data/campus_customs_new.db to <scratch_dir>/scratch.db, starts the MCP
server over stdio pointed at that copy and a scratch approvals store, and runs:
  1. propose_purchase_order vendor 1 -> refused (open invoice 501); vendor 2 -> pending
  2. propose_payment invoice 501 -> pay_approved refused (not approved)
  3. human approval via scripts/approve.py -> pay_approved succeeds
  4. pay_approved again -> refused (double pay)
  5. rent: amount mismatch refused, then correct amount succeeds (next_due advances)
  6. a payment larger than cash -> refused (uses a scratch-only test invoice 9001)
The working copy is never opened for writing.

Usage: .venv/bin/python scripts/write_tool_test.py <scratch_dir>
"""

import asyncio
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import PythonStdioTransport

ROOT = Path(__file__).resolve().parents[1]
WORKING = ROOT / "data" / "campus_customs_new.db"


def dump(db: Path, store: Path, title: str) -> None:
    conn = sqlite3.connect(f"{db.as_uri()}?mode=ro", uri=True)
    print(f"\n----- scratch database {title} -----")
    for sql in ("SELECT * FROM cash_accounts", "SELECT id, vendor_id, amount, due_date, status FROM invoices",
                "SELECT * FROM payments", "SELECT id, monthly_rent, next_due FROM leases"):
        cur = conn.execute(sql)
        print(sql)
        print("  " + " | ".join(d[0] for d in cur.description))
        rows = cur.fetchall()
        for r in rows:
            print("  " + " | ".join(str(v) for v in r))
        if not rows:
            print("  (no rows)")
    conn.close()
    path = store / "approvals.json"
    recs = json.loads(path.read_text()) if path.exists() else []
    print(f"approvals store: {[(r['id'], r['status'], r.get('approved_by')) for r in recs]}")


def approve(store: Path, pid: str, who: str) -> None:
    env = {**os.environ, "CAMPUS_CUSTOMS_STORE_DIR": str(store)}
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "approve.py"), "approve", pid, "--by", who],
                         env=env, capture_output=True, text=True)
    res = json.loads(out.stdout)
    print(f"\n[HUMAN] scripts/approve.py approve {pid} --by {who!r} -> ok={res['ok']} "
          f"status={res.get('proposal', {}).get('status')} approval_path={res.get('proposal', {}).get('approval_path')}")


async def main(scratch: Path) -> int:
    scratch.mkdir(parents=True, exist_ok=True)
    db, store = scratch / "scratch.db", scratch / "store"
    if store.exists():
        shutil.rmtree(store)
    store.mkdir()
    shutil.copyfile(WORKING, db)
    assert db.resolve() != WORKING.resolve()
    # Scratch-only fixture: an invoice larger than the cash that will be left, for the insufficient-cash test.
    with sqlite3.connect(db) as c:
        c.execute("INSERT INTO invoices (id, vendor_id, amount, due_date, status, description) "
                  "VALUES (9001, 3, 3000.0, '2026-09-10', 'open', 'SCRATCH TEST ONLY: larger than cash')")
    print(f"scratch db: {db}\n(scratch-only fixture added: invoice 9001, vendor 3, 3000.0, open)")
    dump(db, store, "BEFORE")

    transport = PythonStdioTransport(ROOT / "mcp_server" / "server.py", python_cmd=sys.executable, keep_alive=False,
                                     env={"PATH": os.environ["PATH"], "CAMPUS_CUSTOMS_DB": str(db),
                                          "CAMPUS_CUSTOMS_STORE_DIR": str(store), "FASTMCP_LOG_LEVEL": "WARNING"})
    async with Client(transport) as client:
        names = sorted(t.name for t in await client.list_tools())
        print(f"\nMCP tools: {names}\nany approval tool exposed over MCP? {any('approv' in n and n != 'pay_approved' for n in names)}")

        async def call(label, tool, **args):
            res = await client.call_tool(tool, args)
            print(f"\n[{label}] {tool}({json.dumps(args)})\n  -> {json.dumps(res.data if res.data is not None else res.structured_content)}")
            return res.data if res.data is not None else res.structured_content

        await call("1a", "propose_purchase_order", vendor_id=1, sku="CC-TEE-WHITE", size="S", qty=12,
                   reason="Restock size S for ticket 101")
        await call("1b", "propose_purchase_order", vendor_id=2, sku="CC-MUG-CREST", size="OS", qty=24,
                   reason="Restock crest mugs (out of stock)")
        p = await call("2a", "propose_payment", kind="invoice", ref_id=501, amount=840.0,
                       reason="Clear overdue invoice 501 so vendor 1 can ship")
        pid = p["proposal"]["id"]
        await call("2b", "pay_approved", proposal_id=pid, amount=840.0)
        approve(store, pid, "Test Approver")
        await call("3", "pay_approved", proposal_id=pid, amount=840.0)
        await call("4", "pay_approved", proposal_id=pid, amount=840.0)
        r = await call("5a", "propose_payment", kind="rent", ref_id=1, amount=2400.0, reason="Rent due 2026-09-02")
        rid = r["proposal"]["id"]
        approve(store, rid, "Test Approver")
        await call("5b", "pay_approved", proposal_id=rid, amount=2000.0)
        await call("5c", "pay_approved", proposal_id=rid, amount=2400.0)
        b = await call("6a", "propose_payment", kind="invoice", ref_id=9001, amount=3000.0, reason="scratch test")
        bid = b["proposal"]["id"]
        approve(store, bid, "Test Approver")
        await call("6b", "pay_approved", proposal_id=bid, amount=3000.0)

    dump(db, store, "AFTER")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(Path(sys.argv[1]))))
