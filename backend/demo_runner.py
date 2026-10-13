"""Scripted dashboard demo, played by the stub runner (tests and screenshots only).

Enabled only when the API is started with CAMPUS_CUSTOMS_STUB_RUNNER_SECONDS > 0 AND
CAMPUS_CUSTOMS_STUB_DEMO=1. It calls no model. It writes audit entries that look like
an agent run (model requests, tool calls, delegations, final answers) so the dashboard
can be built and photographed, and every entry carries run_label "dashboard-demo".
Every agent text it writes starts with "[demo]".

The tool calls are REAL MCP calls (get_ticket, check_stock, propose_payment,
save_customer_draft, resolve_ticket, ...) against the scratch database and stores,
so tool results are real data from the scratch copy. Which agent calls what, and the
delegation order, are scripted.

Safety: assert_all_scratch() refuses unless the working database, the original
database, the store directory and the audit file all resolve OUTSIDE the project
folder. main.py calls it at startup (the server will not start in demo mode
otherwise) and play() calls it again before every run.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from fastmcp import Client

from backend import audit
from backend.agents import MODEL_NAME, mcp_transport
from backend.models import AuditEntry, BossDecision, DecisionAction, Finding, RunOutcome

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEMO_LABEL = "dashboard-demo"


def assert_all_scratch(paths: dict[str, Path]) -> None:
    """Raise unless every path is outside the project (i.e. a scratch copy)."""
    inside = [name for name, p in paths.items() if Path(p).resolve().is_relative_to(PROJECT_ROOT)]
    if inside:
        raise RuntimeError(f"Demo playback refused: {', '.join(inside)} point(s) inside the project, not at scratch copies.")


class _Script:
    """Writes demo audit entries and makes real MCP calls on the scratch copy."""

    def __init__(self, call, run_id: str, ticket_id: int, pause: float):
        self.call, self.run_id, self.ticket_id, self.pause = call, run_id, ticket_id, pause

    def emit(self, agent: str, depth: int, parent: str | None, step: str, *, name: str | None = None,
             arguments: dict | None = None, result: Any = None, stop_reason: str | None = None) -> None:
        audit.append([AuditEntry(
            ts=audit.now_iso(), run_label=DEMO_LABEL, run_id=self.run_id, ticket_id=self.ticket_id,
            agent=agent, depth=depth, parent_agent=parent, step=step, name=name,
            arguments=audit.safe_args(arguments), result_summary=None if result is None else audit.summarize(result),
            stop_reason=stop_reason, model=MODEL_NAME,
        ).model_dump()])

    async def think(self, agent: str, depth: int, parent: str | None) -> None:
        self.emit(agent, depth, parent, "model_request")
        await asyncio.sleep(self.pause)

    async def tool(self, agent: str, depth: int, parent: str | None, tool: str, **args: Any) -> dict:
        self.emit(agent, depth, parent, "tool_call", name=tool, arguments=args)
        await asyncio.sleep(self.pause / 2)
        result = await self.call(tool, **args)
        summary = result
        if isinstance(result, dict) and isinstance(result.get("proposal"), dict):
            p = result["proposal"]
            summary = {"ok": result.get("ok"), "proposal_id": p.get("id"), "kind": p.get("kind"),
                       "amount": p.get("amount", p.get("estimated_cost")), "status": p.get("status")}
        self.emit(agent, depth, parent, "tool_result", name=tool, arguments=args, result=summary)
        await asyncio.sleep(self.pause / 2)
        return result

    async def delegate(self, caller: str, depth: int, target: str, task: str) -> None:
        self.emit(caller, depth, None if depth == 0 else "boss", "delegation",
                  name=f"delegate_to_{target}", arguments={"task": task})
        await asyncio.sleep(self.pause / 2)

    def report(self, agent: str, depth: int, parent: str, summary: str, *, proposal_ids=(), draft_ids=()) -> dict:
        rep = {"agent": agent, "status": "complete", "summary": f"[demo] {summary}",
               "findings": [], "recommended_actions": [], "open_questions": [],
               "proposal_ids": list(proposal_ids), "draft_ids": list(draft_ids)}
        self.emit(agent, depth, parent, "final_answer", name="SpecialistReport",
                  result={"status": "complete", "summary_chars": len(rep["summary"])}, stop_reason="final_answer")
        return rep

    def returned(self, caller: str, depth: int, parent: str | None, target: str, task: str, rep: dict) -> None:
        self.emit(caller, depth, parent, "tool_result", name=f"delegate_to_{target}", arguments={"task": task}, result=rep)


async def _ticket_101(s: _Script) -> BossDecision:
    await s.think("boss", 0, None)
    t = await s.tool("boss", 0, None, "get_ticket", ticket_id=101)
    task_inv = f"Ticket 101: report stock of {t['sku']} size {t['size']} and restock options."
    await s.delegate("boss", 0, "inventory", task_inv)
    await s.think("inventory", 1, "boss")
    stock = await s.tool("inventory", 1, "boss", "check_stock", sku=t["sku"], size=t["size"])
    await s.tool("inventory", 1, "boss", "list_vendors")
    held = await s.tool("inventory", 1, "boss", "get_vendor_open_invoices", vendor_id=1)
    task_acc = "Vendor 1 is on hold by invoice 501; check cash and prepare the invoice payment for human approval."
    await s.delegate("inventory", 1, "accounting", task_acc)
    await s.think("accounting", 2, "inventory")
    inv = await s.tool("accounting", 2, "inventory", "get_invoice", invoice_id=501)
    await s.tool("accounting", 2, "inventory", "get_cash_balance", account="checking")
    prop = await s.tool("accounting", 2, "inventory", "propose_payment", kind="invoice", ref_id=501,
                        amount=inv["amount"], reason="[demo] Clear invoice 501 so vendor 1 can restock size S")
    pid = (prop.get("proposal") or {}).get("id")
    await s.think("accounting", 2, "inventory")
    acc = s.report("accounting", 2, "inventory", f"Proposed paying invoice 501 ({inv['amount']}); waiting for a human.",
                   proposal_ids=[pid] if pid else [])
    s.returned("inventory", 1, "boss", "accounting", task_acc, acc)
    await s.think("inventory", 1, "boss")
    sizes = ", ".join(f"{x['size']} {x['qty']}" for x in stock["all_sizes"] if x["qty"] > 0)
    rep_inv = s.report("inventory", 1, "boss", f"Size S qty {stock['qty']}; in stock: {sizes}. Vendor 1 held by "
                       f"{len(held['open_invoices'])} open invoice(s).", proposal_ids=[pid] if pid else [])
    s.returned("boss", 0, None, "inventory", task_inv, rep_inv)
    await s.think("boss", 0, None)
    task_cs = "Ticket 101: draft a reply offering an in-stock size; size S is out of stock."
    await s.delegate("boss", 0, "customer_service", task_cs)
    await s.think("customer_service", 1, "boss")
    draft = await s.tool("customer_service", 1, "boss", "save_customer_draft", ticket_id=101, recipient=t["requester"],
                         subject="[demo] Your Classic Bulldog Tee",
                         body=f"[demo] Size S is out of stock right now. In stock: {sizes}. Would one of those work?")
    did = (draft.get("draft") or {}).get("id")
    rep_cs = s.report("customer_service", 1, "boss", "Saved a draft offering in-stock sizes.", draft_ids=[did] if did else [])
    s.returned("boss", 0, None, "customer_service", task_cs, rep_cs)
    await s.think("boss", 0, None)
    await s.tool("boss", 0, None, "resolve_ticket", ticket_id=101, status="resolved",
                 resolution_note="[demo] Offered in-stock sizes; invoice 501 payment awaiting human approval.")
    s.emit("boss", 0, None, "final_answer", name="BossDecision", result={"status": "ok", "summary_chars": 0},
           stop_reason="final_answer")
    return BossDecision(
        ticket_id=101, worked_on_by=["boss", "inventory", "accounting", "customer_service"],
        final_decision=f"DEMO (scripted playback, no model): size S has qty {stock['qty']}; a reply offering {sizes} "
                       f"is on the drafts board, and paying invoice 501 to lift the vendor hold is waiting for a human.",
        findings=[Finding(fact=f"CC-TEE-WHITE size S qty {stock['qty']}", source_tool="check_stock")],
        actions=[DecisionAction(description="Reply drafted offering in-stock sizes", owner="customer_service",
                                state="taken", needs_human_approval=True),
                 DecisionAction(description=f"Pay invoice 501 ({inv['amount']})", owner="human", state="proposed",
                                needs_human_approval=True)],
        human_approval_needed=True, approval_items=[pid] if pid else [], ticket_status_set="resolved")


async def _ticket_102(s: _Script) -> BossDecision:
    await s.think("boss", 0, None)
    t = await s.tool("boss", 0, None, "get_ticket", ticket_id=102)
    task_fac = f"Ticket 102: lease {t['lease_id']} rent notice; report due date and whether checking covers it."
    await s.delegate("boss", 0, "facilities", task_fac)
    await s.think("facilities", 1, "boss")
    lease = await s.tool("facilities", 1, "boss", "get_lease", lease_id=t["lease_id"])
    await s.tool("facilities", 1, "boss", "list_payments", kind="rent")
    task_acc = f"Propose the rent payment for lease {t['lease_id']} ({lease['monthly_rent']}) for human approval."
    await s.delegate("facilities", 1, "accounting", task_acc)
    await s.think("accounting", 2, "facilities")
    await s.tool("accounting", 2, "facilities", "get_cash_balance", account="checking")
    prop = await s.tool("accounting", 2, "facilities", "propose_payment", kind="rent", ref_id=t["lease_id"],
                        amount=lease["monthly_rent"], reason=f"[demo] Rent due {lease['next_due']}")
    pid = (prop.get("proposal") or {}).get("id")
    acc = s.report("accounting", 2, "facilities", f"Proposed rent {lease['monthly_rent']}; waiting for a human.",
                   proposal_ids=[pid] if pid else [])
    s.returned("facilities", 1, "boss", "accounting", task_acc, acc)
    rep = s.report("facilities", 1, "boss", f"Rent {lease['monthly_rent']} due {lease['next_due']} "
                   f"({lease['days_until_due']} days). Payment proposed.", proposal_ids=[pid] if pid else [])
    s.returned("boss", 0, None, "facilities", task_fac, rep)
    await s.think("boss", 0, None)
    s.emit("boss", 0, None, "final_answer", name="BossDecision", result={"status": "ok", "summary_chars": 0},
           stop_reason="final_answer")
    return BossDecision(
        ticket_id=102, worked_on_by=["boss", "facilities", "accounting"],
        final_decision=f"DEMO (scripted playback, no model): rent {lease['monthly_rent']} is due {lease['next_due']}; "
                       "the payment is proposed and the ticket stays open until a human approves it.",
        actions=[DecisionAction(description=f"Pay rent {lease['monthly_rent']}", owner="human", state="proposed",
                                needs_human_approval=True)],
        human_approval_needed=True, approval_items=[pid] if pid else [])


async def _ticket_other(s: _Script) -> BossDecision:
    await s.think("boss", 0, None)
    t = await s.tool("boss", 0, None, "get_ticket", ticket_id=s.ticket_id)
    task = f"Ticket {s.ticket_id}: report stock of {t.get('sku')} size {t.get('size')}."
    await s.delegate("boss", 0, "inventory", task)
    await s.think("inventory", 1, "boss")
    stock = await s.tool("inventory", 1, "boss", "check_stock", sku=t.get("sku") or "", size=t.get("size") or "")
    rep = s.report("inventory", 1, "boss", f"qty {stock.get('qty')} on hand.")
    s.returned("boss", 0, None, "inventory", task, rep)
    s.emit("boss", 0, None, "final_answer", name="BossDecision", result={"status": "ok", "summary_chars": 0},
           stop_reason="final_answer")
    return BossDecision(ticket_id=s.ticket_id, worked_on_by=["boss", "inventory"], human_approval_needed=False,
                        final_decision="DEMO (scripted playback, no model): stock checked; no decision taken.")


async def play(ticket_id: int, run_id: str, *, db_path: Path, store_dir: Path, original_db: Path,
               pause: float) -> RunOutcome:
    """Play the scripted demo for one ticket on the scratch copy."""
    assert_all_scratch({"database": db_path, "original database": original_db, "store directory": store_dir,
                        "audit file": audit.AUDIT_TRAIL_PATH})
    async with Client(mcp_transport(db_path, store_dir)) as client:
        async def call(tool: str, **args: Any) -> dict:
            res = await client.call_tool(tool, args)
            return res.data if res.data is not None else res.structured_content
        s = _Script(call, run_id, ticket_id, pause)
        script = {101: _ticket_101, 102: _ticket_102}.get(ticket_id, _ticket_other)
        decision = await script(s)
    return RunOutcome(agent="boss", status="ok", output=decision.model_dump(), run_id=run_id, depth=0, usage={})
