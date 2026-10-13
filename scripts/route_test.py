"""Route tests against a backend instance pointed entirely at scratch copies.

The server under test must be started with CAMPUS_CUSTOMS_DB, CAMPUS_CUSTOMS_ORIGINAL_DB,
CAMPUS_CUSTOMS_STORE_DIR and AUDIT_TRAIL_PATH set to scratch paths and
CAMPUS_CUSTOMS_STUB_RUNNER_SECONDS > 0 (stub runner, no model). This script uses the
same scratch paths (from the same environment variables) to create proposals with
the MCP propose tools and to make scratch-only tweaks. It refuses to run against
the real working database.

Usage: .venv/bin/python scripts/route_test.py http://127.0.0.1:8001
"""

import asyncio
import hashlib
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

import httpx
from fastmcp import Client

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.agents import mcp_transport  # noqa: E402

BASE = sys.argv[1]
DB = Path(os.environ["CAMPUS_CUSTOMS_DB"]).resolve()
ORIGINAL = Path(os.environ["CAMPUS_CUSTOMS_ORIGINAL_DB"]).resolve()
STORE = Path(os.environ["CAMPUS_CUSTOMS_STORE_DIR"]).resolve()
AUDIT = Path(os.environ["AUDIT_TRAIL_PATH"]).resolve()
assert DB.is_relative_to(ROOT) is False and STORE.is_relative_to(ROOT) is False, "scratch paths only"
assert AUDIT.is_relative_to(ROOT) is False, "scratch audit copy only"

http = httpx.Client(base_url=BASE, timeout=60)


def show(label: str, r: httpx.Response) -> dict:
    try:
        body = r.json()
    except ValueError:
        body = r.text
    print(f"\n[{label}] {r.request.method} {r.request.url.path}{'?' + r.request.url.query.decode() if r.request.url.query else ''}"
          f"{'  body=' + r.request.content.decode() if r.request.content else ''}\n  -> HTTP {r.status_code} {json.dumps(body)}")
    return body if isinstance(body, dict) else {}


def db(sql: str, params=()) -> list:
    with sqlite3.connect(f"{DB.as_uri()}?mode=ro", uri=True) as c:
        return c.execute(sql, params).fetchall()


def tweak(sql: str, params=()) -> None:
    """Scratch-only change to the scratch database (never the real one)."""
    assert DB.name != "campus_customs_new.db" or not DB.is_relative_to(ROOT)
    with sqlite3.connect(DB) as c:
        c.execute(sql, params)
    print(f"\n[scratch tweak] {sql} {params}")


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def audit_count() -> int:
    return len(json.loads(AUDIT.read_text()))


async def mcp(tool: str, **args):
    async with Client(mcp_transport(DB, STORE)) as c:
        res = await c.call_tool(tool, args)
        data = res.data if res.data is not None else res.structured_content
    print(f"\n[MCP scratch] {tool}({json.dumps(args)})\n  -> {json.dumps(data)}")
    return data


def section(title: str) -> None:
    print(f"\n{'=' * 20} {title} {'=' * 20}")


def main() -> int:
    show("health", http.get("/api/health"))

    section("APPROVE FLOW")
    asyncio.run(mcp("propose_payment", kind="invoice", ref_id=501, amount=840.0, reason="Clear invoice 501"))
    asyncio.run(mcp("propose_payment", kind="rent", ref_id=1, amount=2400.0, reason="Rent due 2026-09-02"))
    asyncio.run(mcp("propose_purchase_order", vendor_id=2, sku="CC-MUG-CREST", size="OS", qty=24, reason="Restock mugs"))
    show("pending approvals", http.get("/api/approvals", params={"status": "pending"}))
    show("tickets with pending counts", http.get("/api/tickets"))
    print("\nscratch before:", db("SELECT balance FROM cash_accounts"), db("SELECT id, status FROM invoices"), db("SELECT * FROM payments"))
    show("approve invoice proposal", http.post("/api/approvals/PAY-0001/approve", json={"approved_by": "Test Approver"}))
    print("\nscratch after:", db("SELECT balance FROM cash_accounts"), db("SELECT id, status FROM invoices"), db("SELECT * FROM payments"))
    show("approve invoice again", http.post("/api/approvals/PAY-0001/approve", json={"approved_by": "Test Approver"}))
    print("\npayments rows after second approve:", db("SELECT COUNT(*) FROM payments"))
    tweak("UPDATE cash_accounts SET balance = ? WHERE name = 'checking'", (1000.0,))
    show("approve rent with cash short", http.post("/api/approvals/PAY-0002/approve", json={"approved_by": "Test Approver"}))
    show("rent proposal afterwards", http.get("/api/approvals", params={"status": "pending"}))
    print("\nscratch after refusal:", db("SELECT balance FROM cash_accounts"), db("SELECT next_due FROM leases"), db("SELECT COUNT(*) FROM payments"))
    show("cash before PO", http.get("/api/cash"))
    show("approve purchase order", http.post("/api/approvals/PO-0001/approve", json={"approved_by": "Test Approver"}))
    show("cash after PO", http.get("/api/cash"))
    print("\ninventory CC-MUG-CREST OS after PO:", db("SELECT qty FROM inventory WHERE sku='CC-MUG-CREST'"))
    show("reject rent proposal", http.post("/api/approvals/PAY-0002/reject", json={"rejected_by": "Test Approver", "reason": "Pay next week"}))
    show("approve rejected proposal", http.post("/api/approvals/PAY-0002/approve", json={"approved_by": "Test Approver"}))
    asyncio.run(mcp("pay_approved", proposal_id="PAY-0002", amount=2400.0))
    for label, body in [("empty name", {"approved_by": ""}), ("blank name", {"approved_by": "   "}),
                        ("61-char name", {"approved_by": "A" * 61}), ("bad characters", {"approved_by": "R2-D2 <script>"})]:
        show(label, http.post("/api/approvals/PO-0001/approve", json=body))
    show("unknown proposal id", http.post("/api/approvals/PAY-9999/approve", json={"approved_by": "Test Approver"}))
    show("malformed proposal id", http.post("/api/approvals/DROP-TABLE/approve", json={"approved_by": "Test Approver"}))

    section("RUN ROUTE (stub runner)")
    cursor = show("events cursor before run", http.get("/api/events", params={"limit": 1}))["next_cursor"]
    r = show("start run on 101", http.post("/api/tickets/101/run"))
    run_id = r["run_id"]
    seen = []
    second = None
    while True:
        st = http.get(f"/api/runs/{run_id}").json()
        if not seen or seen[-1] != st["status"]:
            seen.append(st["status"])
        if st["status"] == "running" and second is None:
            second = show("second run while running", http.post("/api/tickets/102/run"))
            show("reset while run in progress", http.post("/api/reset", json={"confirm": True}))
        if st["status"] in ("finished", "stopped", "error"):
            break
        time.sleep(0.2)
    print(f"\nstatus values polled: {seen}")
    show("final run record", http.get(f"/api/runs/{run_id}"))
    show("unknown ticket", http.post("/api/tickets/999/run"))
    asyncio.run(mcp("resolve_ticket", ticket_id=103, status="declined", resolution_note="scratch test"))
    show("resolved ticket", http.post("/api/tickets/103/run"))
    show("unknown run id", http.get("/api/runs/0123456789ab"))

    section("EVENTS ROUTE")
    show("events after cursor", http.get("/api/events", params={"after": cursor}))
    show("events filtered by run_id", http.get("/api/events", params={"run_id": run_id}))
    nxt = http.get("/api/events", params={"limit": 1}).json()["next_cursor"]
    show("events after latest cursor (nothing new)", http.get("/api/events", params={"after": nxt}))
    capped = http.get("/api/events", params={"limit": 100000}).json()
    print(f"\n[limit cap] GET /api/events?limit=100000 -> limit={capped['limit']} events returned={len(capped['events'])} total={capped['total']}")
    show("limit 0 rejected", http.get("/api/events", params={"limit": 0}))

    section("RESET ROUTE")
    asyncio.run(mcp("save_customer_draft", ticket_id=101, recipient="Scratch Test", subject="scratch", body="scratch draft"))
    print("\nscratch db sha before reset:", sha(DB), "| original:", sha(ORIGINAL))
    print("stores before reset:", {p.name: len(json.loads(p.read_text())) for p in sorted(STORE.glob("*.json"))})
    show("reset without confirm", http.post("/api/reset", json={}))
    show("reset confirm false", http.post("/api/reset", json={"confirm": False}))
    before = audit_count()
    res = show("reset confirm true", http.post("/api/reset", json={"confirm": True}))
    after = audit_count()
    print(f"\nscratch db sha after reset: {sha(DB)}\noriginal sha:               {sha(ORIGINAL)}\nequal: {sha(DB) == sha(ORIGINAL)}")
    print("stores after reset:", {p.name: json.loads(p.read_text()) for p in sorted(STORE.glob("*.json"))})
    print(f"audit entries before/after reset: {before} -> {after} (+{after - before}); last entry step="
          f"{json.loads(AUDIT.read_text())[-1]['step']} name={json.loads(AUDIT.read_text())[-1]['name']}")
    show("tickets after reset", http.get("/api/tickets"))
    show("cash after reset", http.get("/api/cash"))

    section("VALIDATION AND CORS")
    show("extra field", http.post("/api/approvals/PO-0001/approve", json={"approved_by": "Test Approver", "amount": 1}))
    marker = "ECHO-CHECK-sk-not-a-real-key-123"
    r = http.post("/api/reset", json={"confirm": marker})
    show("invalid body type", r)
    print(f"  input echoed back? {marker in r.text}")
    r = http.post("/api/approvals/PO-0001/approve", content=f'{{"approved_by": "{marker}", ', headers={"Content-Type": "application/json"})
    show("malformed JSON", r)
    print(f"  input echoed back? {marker in r.text}")
    for origin in ("http://localhost:5173", "http://127.0.0.1:5173", "http://evil.example.com"):
        r = http.options("/api/cash", headers={"Origin": origin, "Access-Control-Request-Method": "GET"})
        g = http.get("/api/health", headers={"Origin": origin})
        print(f"\n[CORS] Origin {origin}: preflight HTTP {r.status_code}, allow-origin="
              f"{r.headers.get('access-control-allow-origin')!r}; GET allow-origin={g.headers.get('access-control-allow-origin')!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
