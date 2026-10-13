"""Campus Customs web API for the dashboard (FastAPI).

Start from the backend/ folder:   uvicorn main:app --reload --port 8000

All paths resolve from this file, not the current directory. Every shop read and
write goes through the MCP server (mcp_server/server.py) over stdio, the same way
the agents reach it; the only direct file operation is the reset copy in
scripts/reset_db.py. Only three routes change shop data: run (through the agents),
approve (pay_approved) and reset. The approve route is the only one that moves money.

Environment overrides (tests point everything at scratch copies with these):
  CAMPUS_CUSTOMS_DB, CAMPUS_CUSTOMS_ORIGINAL_DB, CAMPUS_CUSTOMS_STORE_DIR,
  AUDIT_TRAIL_PATH, CAMPUS_CUSTOMS_RUN_LABEL, DASHBOARD_ORIGINS, and
  CAMPUS_CUSTOMS_STUB_RUNNER_SECONDS (tests only: a stub replaces the agent team).
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import logging
import os
import sys
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Any, Literal

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI, HTTPException, Query, Request  # noqa: E402
from fastapi import Path as PathParam  # noqa: E402
from fastapi.exceptions import RequestValidationError  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from fastmcp import Client  # noqa: E402
from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator  # noqa: E402

from backend import approvals, audit  # noqa: E402
from backend.agents import LIMITS, MODEL_NAME, mcp_transport, run_team  # noqa: E402
from backend.models import AuditEntry, BossDecision, RunOutcome  # noqa: E402
from mcp_server import stores  # noqa: E402

logger = logging.getLogger("campus_customs.api")


def _load_reset_module():
    spec = importlib.util.spec_from_file_location("reset_db", PROJECT_ROOT / "scripts" / "reset_db.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


reset_db = _load_reset_module()

# --- configuration -------------------------------------------------------------
DB_PATH = Path(os.environ.get("CAMPUS_CUSTOMS_DB") or PROJECT_ROOT / "data" / "campus_customs_new.db").resolve()
STORE_DIR = stores.STORE_DIR
RUN_LABEL = os.environ.get("CAMPUS_CUSTOMS_RUN_LABEL", "dashboard")
STUB_RUNNER_SECONDS = float(os.environ.get("CAMPUS_CUSTOMS_STUB_RUNNER_SECONDS") or 0)
# Tests/screenshots only: the stub runner plays the scripted demo in backend/demo_runner.py.
STUB_DEMO = STUB_RUNNER_SECONDS > 0 and os.environ.get("CAMPUS_CUSTOMS_STUB_DEMO") == "1"
ORIGINS = [o.strip() for o in os.environ.get(
    "DASHBOARD_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()]
if DB_PATH.name == "campus_customs.db":
    raise RuntimeError("The API must never point at the original campus_customs.db.")
if "*" in ORIGINS:
    raise RuntimeError("DASHBOARD_ORIGINS may not contain a wildcard.")
if STUB_DEMO:
    from backend import demo_runner
    demo_runner.assert_all_scratch({"database": DB_PATH, "original database": reset_db.ORIGINAL_DB,
                                    "store directory": STORE_DIR, "audit file": audit.AUDIT_TRAIL_PATH})

TICKET_PROMPT = (
    "Work ticket {ticket_id}. Read it with get_ticket, decide who should handle it, delegate "
    "under the shop rules, and return your decision."
)
EVENTS_MAX_LIMIT = 500
PROPOSAL_ID = r"^(PAY|PO)-\d{4,6}$"
RUN_ID = r"^[a-f0-9]{12}$"


# --- MCP access ------------------------------------------------------------------


@asynccontextmanager
async def mcp_session():
    """One MCP client session (a short-lived server subprocess) for a request."""
    async with Client(mcp_transport(DB_PATH, STORE_DIR)) as client:
        async def call(tool: str, **args: Any) -> dict[str, Any]:
            res = await client.call_tool(tool, args)
            return res.data if res.data is not None else res.structured_content
        yield call


async def mcp_call(tool: str, **args: Any) -> dict[str, Any]:
    async with mcp_session() as call:
        return await call(tool, **args)


# --- run state (in memory: one run at a time) --------------------------------------

RUNS: dict[str, dict[str, Any]] = {}
_tasks: set[asyncio.Task] = set()
_state_lock = asyncio.Lock()  # guards starting a run, approving, and resetting
_current_run: str | None = None


def _now() -> str:
    return audit.now_iso()


def _set_status(rec: dict[str, Any], status: str, **extra: Any) -> None:
    rec.update(status=status, **extra)
    rec["history"].append({"status": status, "at": _now()})


async def default_runner(ticket_id: int, run_id: str) -> RunOutcome:
    """The real runner: the Problem 5 Boss entry point with the full team."""
    return await run_team(TICKET_PROMPT.format(ticket_id=ticket_id), run_label=RUN_LABEL, ticket_id=ticket_id,
                          start_agent="boss", db_path=DB_PATH, store_dir=STORE_DIR, run_id=run_id)


def _stub_note(run_id: str, ticket_id: int, text: str) -> None:
    audit.append([AuditEntry(
        ts=_now(), run_label=RUN_LABEL, run_id=run_id, ticket_id=ticket_id, agent=None, depth=None,
        parent_agent=None, step="note", name="stub_runner", result_summary=text, model=MODEL_NAME,
    ).model_dump()])


async def stub_runner(ticket_id: int, run_id: str) -> RunOutcome:
    """Test-only stand-in for the agent team: no model. Plain mode just waits; demo mode
    (CAMPUS_CUSTOMS_STUB_DEMO=1) plays the scripted demo on scratch copies only."""
    if STUB_DEMO:
        return await demo_runner.play(ticket_id, run_id, db_path=DB_PATH, store_dir=STORE_DIR,
                                      original_db=reset_db.ORIGINAL_DB, pause=STUB_RUNNER_SECONDS)
    _stub_note(run_id, ticket_id, "stub run started (no agent or model was called)")
    await asyncio.sleep(STUB_RUNNER_SECONDS)
    _stub_note(run_id, ticket_id, "stub run finished")
    decision = BossDecision(ticket_id=ticket_id, worked_on_by=["boss"], human_approval_needed=False,
                            final_decision="STUB: no agents were run.")
    return RunOutcome(agent="boss", status="ok", output=decision.model_dump(), run_id=run_id, depth=0, usage={})


RUNNER = stub_runner if STUB_RUNNER_SECONDS > 0 else default_runner


async def _execute(rec: dict[str, Any]) -> None:
    global _current_run
    try:
        _set_status(rec, "running")
        outcome = await RUNNER(rec["ticket_id"], rec["run_id"])
        rec["usage"] = outcome.usage
        if outcome.status == "ok":
            _set_status(rec, "finished", decision=outcome.output)
        else:
            _set_status(rec, "stopped", reason=outcome.status.removeprefix("stopped: "))
    except Exception as exc:  # noqa: BLE001
        logger.warning("run %s failed: %s", rec["run_id"], type(exc).__name__)
        _set_status(rec, "error", reason="The run failed unexpectedly; see server logs.")
    finally:
        rec["finished_at"] = _now()
        _current_run = None


def _run_view(rec: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in rec.items() if not k.startswith("_")}


# --- request bodies -------------------------------------------------------------------


def _person(value: str, field: str) -> str:
    value = (value or "").strip()
    if not 1 <= len(value) <= 60:
        raise ValueError(f"{field} must be 1 to 60 characters after trimming")
    if not approvals._NAME_RE.match(value):
        raise ValueError(f"{field} must be a person's name (letters, spaces, . ' -)")
    return value


class ApproveBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approved_by: str = Field(max_length=200)

    @field_validator("approved_by")
    @classmethod
    def _name(cls, v: str) -> str:
        return _person(v, "approved_by")


class RejectBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rejected_by: str = Field(max_length=200)
    reason: str | None = Field(default=None, max_length=200)

    @field_validator("rejected_by")
    @classmethod
    def _name(cls, v: str) -> str:
        return _person(v, "rejected_by")


class ResetBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirm: StrictBool


# --- app -----------------------------------------------------------------------------

app = FastAPI(title="Campus Customs desk API", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=ORIGINS, allow_methods=["GET", "POST"],
                   allow_headers=["Content-Type"], allow_credentials=False)


@app.exception_handler(RequestValidationError)
async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    # Never echo the submitted input back: keep only where and what kind of problem.
    errors = [{"loc": list(e.get("loc", [])), "msg": e.get("msg", "invalid"), "type": e.get("type", "")}
              for e in exc.errors()]
    for e in errors:
        e["msg"] = e["msg"].removeprefix("Value error, ")
    return JSONResponse(status_code=422, content={"detail": errors})


@app.exception_handler(Exception)
async def _unexpected_error(_: Request, exc: Exception) -> JSONResponse:
    logger.warning("unexpected error: %s", type(exc).__name__)
    return JSONResponse(status_code=500, content={"detail": "Internal server error."})


def _read_audit() -> list[dict[str, Any]]:
    path = audit.AUDIT_TRAIL_PATH
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    return data if isinstance(data, list) else []


def _proposal_origins() -> dict[str, dict[str, Any]]:
    """proposal id -> {agent, ticket_id, run_id}, from the audit trail's propose_* results."""
    out: dict[str, dict[str, Any]] = {}
    for e in _read_audit():
        if e.get("step") == "tool_result" and str(e.get("name", "")).startswith("propose_"):
            try:
                pid = json.loads(e.get("result_summary") or "{}").get("proposal_id")
            except (json.JSONDecodeError, AttributeError):
                pid = None
            if pid:
                out[pid] = {"agent": e.get("agent"), "ticket_id": e.get("ticket_id"), "run_id": e.get("run_id")}
    return out


def _target(p: dict[str, Any]) -> str:
    if p.get("kind") == "payment":
        return f"{'invoice' if p.get('payment_kind') == 'invoice' else 'lease'} {p.get('ref_id')}"
    return f"vendor {p.get('vendor_id')} ({p.get('vendor_name')}): {p.get('qty')} x {p.get('sku')} {p.get('size')}"


def _ticket_for(p: dict[str, Any], tickets: list[dict[str, Any]], origins: dict[str, dict]) -> int | None:
    """The ticket a proposal belongs to: from the agent run that made it, else by its linked row."""
    origin = origins.get(p.get("id"), {})
    if origin.get("ticket_id"):
        return origin["ticket_id"]
    for t in tickets:
        if p.get("kind") == "payment" and p.get("payment_kind") == "invoice" and p.get("ref_id") == t.get("invoice_id"):
            return t["id"]
        if p.get("kind") == "payment" and p.get("payment_kind") == "rent" and p.get("ref_id") == t.get("lease_id"):
            return t["id"]
        if p.get("kind") == "purchase_order" and (p.get("sku"), p.get("size")) == (t.get("sku"), t.get("size")):
            return t["id"]
    return None


# --- routes --------------------------------------------------------------------------


@app.get("/api/health")
async def health() -> dict[str, Any]:
    """Extra: liveness and configuration summary (no secrets)."""
    inside = DB_PATH.is_relative_to(PROJECT_ROOT)
    return {
        "ok": True,
        "model": MODEL_NAME,
        "database": str(DB_PATH.relative_to(PROJECT_ROOT)) if inside else "override (outside project)",
        "stores": str(STORE_DIR.relative_to(PROJECT_ROOT)) if STORE_DIR.is_relative_to(PROJECT_ROOT) else "override (outside project)",
        "runner": f"{RUNNER.__module__}.{RUNNER.__qualname__}" + (" (scripted demo playback)" if STUB_DEMO else ""),
        "run_in_progress": _current_run,
        "limits": asdict(LIMITS),
        "cors_origins": ORIGINS,
    }


@app.get("/api/tickets")
async def list_tickets() -> dict[str, Any]:
    async with mcp_session() as call:
        tickets = (await call("list_tickets"))["tickets"]
        pending = (await call("list_proposals", status="pending"))["proposals"]
    origins = _proposal_origins()
    out = []
    for t in tickets:
        ids = [p["id"] for p in pending if _ticket_for(p, tickets, origins) == t["id"]]
        out.append({"id": t["id"], "type": t["type"], "requester": t["requester"], "subject": t["subject"],
                    "status": t["status"], "resolution_note": (t.get("resolution") or {}).get("note"),
                    "pending_approvals": len(ids), "pending_approval_ids": ids})
    return {"tickets": out}


@app.post("/api/tickets/{ticket_id}/run", status_code=202)
async def start_run(ticket_id: int = PathParam(ge=1, le=999_999)) -> dict[str, Any]:
    global _current_run
    async with _state_lock:
        if _current_run is not None:
            raise HTTPException(409, f"A run is already in progress (run_id {_current_run}); wait for it to finish.")
        ticket = await mcp_call("get_ticket", ticket_id=ticket_id)
        if not ticket.get("found"):
            raise HTTPException(404, f"Ticket {ticket_id} not found.")
        if ticket["status"] != "open":
            raise HTTPException(409, f"Ticket {ticket_id} is {ticket['status']!r}, not open; it cannot be run.")
        run_id = uuid.uuid4().hex[:12]
        rec = {"run_id": run_id, "ticket_id": ticket_id, "status": "queued", "history": [], "created_at": _now(),
               "finished_at": None, "decision": None, "reason": None, "usage": None}
        rec["history"].append({"status": "queued", "at": rec["created_at"]})
        RUNS[run_id] = rec
        _current_run = run_id
        task = asyncio.create_task(_execute(rec))
        _tasks.add(task)
        task.add_done_callback(_tasks.discard)
    return {"run_id": run_id, "ticket_id": ticket_id, "status": "queued", "status_url": f"/api/runs/{run_id}"}


@app.get("/api/runs/{run_id}")
async def get_run(run_id: str = PathParam(pattern=RUN_ID)) -> dict[str, Any]:
    rec = RUNS.get(run_id)
    if rec is None:
        raise HTTPException(404, "Unknown run_id (runs are kept in memory until the server restarts).")
    return _run_view(rec)


@app.get("/api/events")
async def events(after: int | None = Query(None, ge=0, le=10_000_000),
                 limit: int = Query(100, ge=1, le=1_000_000),
                 run_id: str | None = Query(None, pattern=r"^[A-Za-z0-9_-]{1,64}$")) -> dict[str, Any]:
    limit = min(limit, EVENTS_MAX_LIMIT)
    data = _read_audit()
    indexed = [(i, e) for i, e in enumerate(data) if run_id is None or e.get("run_id") == run_id]
    if after is None:
        picked = indexed[-limit:]
        next_cursor = len(data)
    else:
        newer = [(i, e) for i, e in indexed if i >= after]
        picked = newer[:limit]
        next_cursor = picked[-1][0] + 1 if len(newer) > limit else len(data)
    return {
        "events": [{
            "seq": i, "ts": e.get("ts"), "run_id": e.get("run_id"), "run_label": e.get("run_label"),
            "ticket_id": e.get("ticket_id"), "agent": e.get("agent"), "depth": e.get("depth"),
            "parent_agent": e.get("parent_agent"), "step": e.get("step"), "name": e.get("name"),
            "summary": e.get("result_summary") or e.get("stop_reason"), "stop_reason": e.get("stop_reason"),
            "usage": e.get("usage"),
        } for i, e in picked],
        "next_cursor": next_cursor,
        "total": len(data),
        "limit": limit,
    }


@app.get("/api/approvals")
async def list_approvals(status: Literal["pending", "approved", "rejected", "executed"] | None = None) -> dict[str, Any]:
    """Extra: proposals (by status) with what they are for and which agent proposed them."""
    async with mcp_session() as call:
        args = {"status": status} if status else {}
        proposals = (await call("list_proposals", **args))["proposals"]
        tickets = (await call("list_tickets"))["tickets"]
    origins = _proposal_origins()
    out = []
    for p in proposals:
        out.append({
            "id": p["id"], "kind": p["kind"], "payment_kind": p.get("payment_kind"), "status": p["status"],
            "amount": p.get("amount", p.get("estimated_cost")), "target": _target(p),
            "vendor_id": p.get("vendor_id"), "ref_id": p.get("ref_id"), "reason": p.get("reason"),
            "expected_arrival": p.get("expected_arrival"), "created_at": p.get("created_at"),
            "proposed_by": origins.get(p["id"], {}).get("agent") or "unknown (not proposed through an agent run)",
            "ticket_id": _ticket_for(p, tickets, origins), "approved_by": p.get("approved_by"),
            "failures": p.get("failures", []),
        })
    return {"approvals": out}


@app.post("/api/approvals/{proposal_id}/approve")
async def approve(body: ApproveBody, proposal_id: str = PathParam(pattern=PROPOSAL_ID)):
    """The only route that moves money: human approval, then pay_approved through MCP."""
    async with _state_lock:
        async with mcp_session() as call:
            matches = [p for p in (await call("list_proposals"))["proposals"] if p["id"] == proposal_id]
            if not matches:
                raise HTTPException(404, f"No proposal with id {proposal_id}.")
            p = matches[0]
            if p["status"] != "pending":
                raise HTTPException(409, f"{proposal_id} is {p['status']!r}, not pending; it cannot be approved again.")

            if p["kind"] != "payment":
                decided = approvals.decide(proposal_id, body.approved_by, approve=True)
                if not decided["ok"]:
                    raise HTTPException(409, decided["reason"])
                return {"ok": True, "kind": p["kind"], "proposal": decided["proposal"],
                        "note": "Purchase order approved by a human. No money moved and inventory is unchanged."}

            cash_before = await call("get_cash_balance", account=p["account"])
            decided = approvals.decide(proposal_id, body.approved_by, approve=True)
            if not decided["ok"]:
                raise HTTPException(409, decided["reason"])
            try:
                result = await call("pay_approved", proposal_id=proposal_id, amount=p["amount"])
            except Exception as exc:  # noqa: BLE001
                logger.warning("pay_approved call failed: %s", type(exc).__name__)
                approvals.revert_to_pending(proposal_id, "payment call failed", body.approved_by)
                raise HTTPException(502, "The payment could not be executed; the proposal is back to pending.")
            if not result.get("ok"):
                reverted = approvals.revert_to_pending(proposal_id, result.get("reason", "refused"), body.approved_by)
                return JSONResponse(status_code=409, content={
                    "ok": False, "refused": True, "reason": result.get("reason"),
                    "proposal_status": (reverted.get("proposal") or {}).get("status"),
                    "note": "Payment refused; the approval was undone and the proposal is back to pending.",
                    "cash": {"balance": cash_before.get("balance"), "as_of": cash_before.get("date")},
                })
            cash_after = await call("get_cash_balance", account=p["account"])
            return {"ok": True, "kind": "payment", "approved_by": body.approved_by, "payment": result["payment"],
                    "effect": result["effect"], "cash_before": cash_before.get("balance"),
                    "cash_after": cash_after.get("balance"), "proposal_id": proposal_id}


@app.post("/api/approvals/{proposal_id}/reject")
async def reject(body: RejectBody, proposal_id: str = PathParam(pattern=PROPOSAL_ID)) -> dict[str, Any]:
    async with _state_lock:
        matches = [p for p in (await mcp_call("list_proposals"))["proposals"] if p["id"] == proposal_id]
        if not matches:
            raise HTTPException(404, f"No proposal with id {proposal_id}.")
        if matches[0]["status"] != "pending":
            raise HTTPException(409, f"{proposal_id} is {matches[0]['status']!r}, not pending; it cannot be rejected.")
        decided = approvals.decide(proposal_id, body.rejected_by, approve=False, reason=body.reason)
        if not decided["ok"]:
            raise HTTPException(409, decided["reason"])
        return {"ok": True, "proposal": decided["proposal"], "note": "Rejected. This proposal can never be paid."}


@app.get("/api/cash")
async def cash() -> dict[str, Any]:
    res = await mcp_call("get_cash_balance", account="checking")
    if not res.get("found"):
        raise HTTPException(404, "No checking account found.")
    return {"account": res["name"], "balance": res["balance"], "as_of": res["date"]}


@app.get("/api/drafts")
async def drafts(ticket_id: int | None = Query(None, ge=1, le=999_999)) -> dict[str, Any]:
    """Extra: customer drafts saved on the board (never sent)."""
    args = {"ticket_id": ticket_id} if ticket_id else {}
    return {"drafts": (await mcp_call("list_drafts", **args))["drafts"]}


@app.post("/api/reset")
async def reset(body: ResetBody) -> dict[str, Any]:
    if not body.confirm:
        raise HTTPException(400, "Reset needs {\"confirm\": true}.")
    async with _state_lock:
        if _current_run is not None:
            raise HTTPException(409, f"A run is in progress (run_id {_current_run}); reset refused.")
        started = time.monotonic()
        result = await asyncio.to_thread(reset_db.reset_database, RUN_LABEL, "api")
        result["duration_ms"] = int((time.monotonic() - started) * 1000)
        return result
