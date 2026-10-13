"""The Campus Customs agent team: five PydanticAI agents on one shared model.

- One model constant (MODEL_NAME) and one shared model object, through the
  Portkey gateway, wired like homework-4/backend/agent.py but pinned.
- One MCP connection (stdio subprocess running mcp_server/server.py) is the only
  way any agent reaches shop data. Each agent sees a filtered view of it
  (TOOL_SCOPES), so e.g. only Accounting can propose payments and only the Boss
  can resolve tickets. That filtering is enforced in code.
- Every agent can delegate to each of the other four (20 directed links). A
  delegation runs the other agent with the parent's usage, so one budget
  (LIMITS) covers the whole top-level run.
- Every loop step is written to output/audit_trail.json (backend/audit.py).
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from dotenv import load_dotenv
from fastmcp.client.transports import PythonStdioTransport
from openai import AsyncOpenAI
from pydantic_ai import Agent, RunContext, Tool
from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.messages import ToolCallPart
from pydantic_ai.models.openai import OpenAIResponsesModel, OpenAIResponsesModelSettings
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import RunUsage, UsageLimits

from backend import audit
from backend.models import (
    AGENT_NAMES,
    AgentName,
    AuditEntry,
    BossDecision,
    RunOutcome,
    SpecialistReport,
    TeamDeps,
    TicketState,
)

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
PROMPTS_DIR = HERE / "prompts"
MCP_SERVER_PATH = PROJECT_ROOT / "mcp_server" / "server.py"

load_dotenv(PROJECT_ROOT / ".env")

# --- the one model -------------------------------------------------------------
MODEL_NAME = "gpt-6-luna"  # the only model any agent may use
audit.set_pinned_model(MODEL_NAME)
PORTKEY_BASE_URL = "https://api.portkey.ai/v1"
PORTKEY_PROVIDER = "openai"


# --- limits (one config block) ---------------------------------------------------
@dataclass(frozen=True)
class TeamLimits:
    max_delegation_depth: int = 3  # boss (depth 0) -> 1 -> 2 -> 3, no deeper
    max_delegations_per_run: int = 8  # total delegate_to_* calls per top-level run (one ticket)
    request_limit: int = 40  # model requests per top-level run, shared by all agents
    tool_calls_limit: int = 60  # tool calls (MCP + delegation) per top-level run, shared
    total_tokens_limit: int = 400_000  # input + output tokens per top-level run, shared
    output_tokens_per_request: int = 4_000  # max_tokens on every model request (includes reasoning tokens)
    reasoning_effort: str = "none"  # "low" sometimes looped in hidden reasoning until the cap; "none" is cheap and stable
    run_timeout_s: float = 240.0  # wall clock per agent run (each delegation gets its own)
    retries: int = 1  # output-validation retries per agent


LIMITS = TeamLimits()

# --- which MCP tools each agent may see (enforced by filtering the toolset) --------
_COMMON = {"get_today", "get_ticket", "list_open_tickets"}
TOOL_SCOPES: dict[AgentName, frozenset[str]] = {
    "boss": frozenset(_COMMON | {
        "check_stock", "get_lease", "get_pricing", "list_vendors", "get_vendor_open_invoices",
        "get_invoice", "get_cash_balance", "list_payments", "list_proposals", "resolve_ticket",
    }),
    "inventory": frozenset(_COMMON | {"check_stock", "get_pricing", "list_vendors", "get_vendor_open_invoices"}),
    "accounting": frozenset(_COMMON | {
        "get_pricing", "get_cash_balance", "get_invoice", "get_vendor_open_invoices", "list_vendors",
        "list_payments", "list_proposals", "get_lease", "check_stock",
        "propose_payment", "propose_purchase_order", "pay_approved",
    }),
    "facilities": frozenset(_COMMON | {"get_lease", "get_cash_balance", "list_payments", "list_proposals"}),
    "customer_service": frozenset(_COMMON | {"check_stock", "get_pricing", "save_customer_draft"}),
}

OUTPUT_TYPES = {name: (BossDecision if name == "boss" else SpecialistReport) for name in AGENT_NAMES}

DELEGATE_DESCRIPTIONS: dict[AgentName, str] = {
    "boss": "Ask the Boss to make a call that is above your scope (priorities, trade-offs, closing a ticket).",
    "inventory": "Ask Inventory about stock by SKU and size, shortfalls, and which vendor can restock and how fast.",
    "accounting": "Ask Accounting about cash, invoices, margins, or to prepare a payment or purchase order for human approval.",
    "facilities": "Ask Facilities about the shop space: the lease, rent amount, due date and whether it is overdue.",
    "customer_service": "Ask Customer Service to draft a message to a customer (saved as a draft, never sent).",
}


def build_shared_model() -> OpenAIResponsesModel:
    """The single model object every agent uses (Portkey gateway, pinned model)."""
    api_key = os.getenv("PORTKEY_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("PORTKEY_API_KEY is not set in .env; the team cannot call the model.")
    client = AsyncOpenAI(
        api_key=api_key,
        base_url=PORTKEY_BASE_URL,
        default_headers={"x-portkey-provider": PORTKEY_PROVIDER},
    )
    return OpenAIResponsesModel(MODEL_NAME, provider=OpenAIProvider(openai_client=client))


# --- audit helpers ---------------------------------------------------------------


def _usage_dict(usage: RunUsage | None) -> dict[str, int] | None:
    if usage is None:
        return None
    return {"requests": usage.requests, "tool_calls": usage.tool_calls,
            "input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens}


def _audit(deps: TeamDeps, step: str, *, name: str | None = None, arguments: dict | None = None,
           result: Any = None, usage: RunUsage | None = None, stop_reason: str | None = None) -> None:
    entry = AuditEntry(
        ts=audit.now_iso(), run_label=deps.state.run_label, run_id=deps.state.run_id,
        ticket_id=deps.state.ticket_id, agent=deps.agent, depth=deps.depth, parent_agent=deps.parent,
        step=step, name=name, arguments=audit.safe_args(arguments),
        result_summary=None if result is None else audit.summarize(result),
        usage=_usage_dict(usage), stop_reason=stop_reason, model=MODEL_NAME,
    )
    audit.append([entry.model_dump()])


def _stopped(reason: str) -> dict[str, Any]:
    return {"status": f"stopped: {reason}"}


# --- MCP connection ----------------------------------------------------------------


async def _mcp_tool_hook(ctx: RunContext[TeamDeps], call_tool, name: str, args: dict[str, Any]):
    """Wraps every MCP tool call: loop protection, then the call, then an audit entry."""
    deps = ctx.deps
    signature = (name, json.dumps(args, sort_keys=True, default=str))
    if signature in deps.seen_tool_calls:
        reason = f"identical call to {name} already made in this run; reuse the earlier result"
        _audit(deps, "limit_stop", name=name, arguments=args, usage=ctx.usage, stop_reason=reason)
        return {"ok": False, "refused": True, "reason": f"stopped: {reason}"}
    deps.seen_tool_calls.add(signature)
    try:
        result = await call_tool(name, args)
    except Exception as exc:
        _audit(deps, "error", name=name, arguments=args, result=type(exc).__name__, usage=ctx.usage)
        raise
    summary = result
    if isinstance(result, dict) and isinstance(result.get("proposal"), dict):
        prop = result["proposal"]  # compact, so the id survives summary truncation (dashboard shows who proposed it)
        summary = {"ok": result.get("ok"), "proposal_id": prop.get("id"), "kind": prop.get("kind"),
                   "amount": prop.get("amount", prop.get("estimated_cost")), "status": prop.get("status")}
    _audit(deps, "tool_result", name=name, arguments=args, result=summary, usage=ctx.usage)
    return result


def mcp_transport(db_path: Path | None = None, store_dir: Path | None = None) -> PythonStdioTransport:
    """A stdio transport that starts mcp_server/server.py (used by the agents and the backend).

    db_path / store_dir point the server at a scratch database and store (tests).
    The subprocess gets only what it needs: no API keys are passed to it.
    """
    env = {"PATH": os.environ.get("PATH", ""), "HOME": os.environ.get("HOME", ""), "FASTMCP_LOG_LEVEL": "WARNING",
           "PYTHONDONTWRITEBYTECODE": "1"}
    if db_path is not None:
        env["CAMPUS_CUSTOMS_DB"] = str(Path(db_path).resolve())
    if store_dir is not None:
        env["CAMPUS_CUSTOMS_STORE_DIR"] = str(Path(store_dir).resolve())
    return PythonStdioTransport(
        MCP_SERVER_PATH, python_cmd=sys.executable, env=env, cwd=str(PROJECT_ROOT), keep_alive=False,
    )


def build_mcp_toolset(db_path: Path | None = None, store_dir: Path | None = None) -> MCPToolset:
    """One stdio MCP connection to mcp_server/server.py for the agent team."""
    return MCPToolset(mcp_transport(db_path, store_dir), process_tool_call=_mcp_tool_hook,
                      tool_error_behavior="failed", max_retries=1)


# --- the team ----------------------------------------------------------------------


class Team:
    """Five agents sharing one model and one MCP connection, fully connected."""

    def __init__(self, mcp_toolset: MCPToolset, model: Any | None = None, limits: TeamLimits = LIMITS):
        self.limits = limits
        self.mcp = mcp_toolset
        self.model = model if model is not None else build_shared_model()
        self.usage_limits = UsageLimits(
            request_limit=limits.request_limit,
            tool_calls_limit=limits.tool_calls_limit,
            total_tokens_limit=limits.total_tokens_limit,
        )
        self.agents: dict[AgentName, Agent] = {name: self._build_agent(name) for name in AGENT_NAMES}

    def _build_agent(self, name: AgentName) -> Agent:
        allowed = TOOL_SCOPES[name]
        scoped_mcp = self.mcp.filtered(lambda ctx, tool_def: tool_def.name in allowed)
        delegate_tools = [self._delegate_tool(name, other) for other in AGENT_NAMES if other != name]
        agent = Agent(
            self.model,
            name=name,
            instructions=(PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8"),
            output_type=OUTPUT_TYPES[name],
            deps_type=TeamDeps,
            toolsets=[scoped_mcp],
            tools=delegate_tools,
            model_settings=OpenAIResponsesModelSettings(
                max_tokens=self.limits.output_tokens_per_request,
                openai_reasoning_effort=self.limits.reasoning_effort,
            ),
            retries=self.limits.retries,
        )

        @agent.instructions
        def _run_context(ctx: RunContext[TeamDeps]) -> str:
            d = ctx.deps
            caller = d.parent or "the human operator"
            left = self.limits.max_delegation_depth - d.depth
            return (
                f"Run context: you are the {name} agent, called by {caller}, at delegation depth "
                f"{d.depth} of {self.limits.max_delegation_depth} ({left} more level(s) of delegation allowed below you). "
                f"Ticket in scope: {d.state.ticket_id if d.state.ticket_id is not None else 'none'}."
            )

        return agent

    def _delegate_tool(self, caller: AgentName, target: AgentName) -> Tool:
        async def delegate(ctx: RunContext[TeamDeps], task: str) -> dict[str, Any]:
            """Hand a clear, self-contained task to another agent and get its typed report back.

            Args:
                task: What you need, with every id, SKU, size and amount it needs. The other agent
                    cannot see your conversation.
            """
            return await self._delegate(ctx, target, task)

        return Tool(delegate, takes_ctx=True, name=f"delegate_to_{target}",
                    description=DELEGATE_DESCRIPTIONS[target])

    async def _delegate(self, ctx: RunContext[TeamDeps], target: AgentName, task: str) -> dict[str, Any]:
        deps, state = ctx.deps, ctx.deps.state
        name = f"delegate_to_{target}"
        args = {"task": task}
        reason = None
        if state.stopped:
            reason = state.stopped
        elif deps.depth + 1 > self.limits.max_delegation_depth:
            reason = f"max delegation depth {self.limits.max_delegation_depth} reached"
        elif state.delegations >= self.limits.max_delegations_per_run:
            reason = f"max {self.limits.max_delegations_per_run} delegations per run reached"
        else:
            signature = (deps.agent, target, " ".join(task.split()).lower())
            if signature in state.delegation_signatures:
                reason = f"identical delegation to {target} already made; reuse the earlier report"
            else:
                state.delegation_signatures.add(signature)
        if reason:
            _audit(deps, "limit_stop", name=name, arguments=args, usage=ctx.usage, stop_reason=reason)
            return _stopped(reason)

        state.delegations += 1
        _audit(deps, "delegation", name=name, arguments=args, usage=ctx.usage)
        child = TeamDeps(agent=target, depth=deps.depth + 1, parent=deps.agent, state=state)
        outcome = await self.run_agent(target, task, child, usage=ctx.usage)
        result = outcome.output if outcome.status == "ok" and outcome.output else {"status": outcome.status}
        _audit(deps, "tool_result", name=name, arguments=args, result=result, usage=ctx.usage)
        return result

    async def run_agent(self, name: AgentName, prompt: str, deps: TeamDeps,
                        usage: RunUsage | None = None) -> RunOutcome:
        """Run one agent loop with auditing, limits and a wall-clock timeout. Never raises."""
        agent = self.agents[name]
        usage = usage if usage is not None else RunUsage()
        output_tool_names: set[str] = {"final_result"}
        status, output, stop_reason = "ok", None, "final_answer"
        try:
            async with asyncio.timeout(self.limits.run_timeout_s):
                async with agent.iter(prompt, deps=deps, usage=usage, usage_limits=self.usage_limits) as run:
                    async for node in run:
                        if Agent.is_model_request_node(node):
                            _audit(deps, "model_request", usage=run.usage)
                        elif Agent.is_call_tools_node(node):
                            for part in node.model_response.parts:
                                if not isinstance(part, ToolCallPart):
                                    continue
                                if part.tool_name in output_tool_names or part.tool_name.startswith("final_result"):
                                    continue
                                if part.tool_name.startswith("delegate_to_"):
                                    continue  # logged as a delegation by _delegate
                                _audit(deps, "tool_call", name=part.tool_name,
                                       arguments=part.args_as_dict(), usage=run.usage)
                    output = run.result.output.model_dump()
                    _audit(deps, "final_answer", name=type(run.result.output).__name__,
                           result={"status": output.get("status", "ok"), "summary_chars":
                                   len(output.get("summary") or output.get("final_decision") or "")},
                           usage=run.usage, stop_reason="final_answer")
        except UsageLimitExceeded as exc:
            detail = str(exc).split(". ")[0]  # e.g. "The next request would exceed the request_limit of 40"
            status = stop_reason = f"stopped: usage limit ({detail})"
            deps.state.stopped = deps.state.stopped or f"usage limit ({detail})"
            _audit(deps, "limit_stop", usage=usage, stop_reason=stop_reason)
        except TimeoutError:
            status = stop_reason = f"stopped: {self.limits.run_timeout_s:.0f}s timeout"
            _audit(deps, "limit_stop", usage=usage, stop_reason=stop_reason)
        except Exception as exc:  # noqa: BLE001 - provider or tool failure: stop cleanly
            status = stop_reason = f"stopped: error {type(exc).__name__}"
            # Only the class and HTTP status: raw provider/tool error text is never logged.
            code = getattr(exc, "status_code", None)
            _audit(deps, "error", result=type(exc).__name__ + (f" (HTTP {code})" if code else ""),
                   usage=usage, stop_reason=stop_reason)
        return RunOutcome(agent=name, status=status, output=output, run_id=deps.state.run_id,
                          depth=deps.depth, usage=_usage_dict(usage) or {})


async def run_team(prompt: str, *, run_label: str, ticket_id: int | None = None,
                   start_agent: AgentName = "boss", db_path: Path | None = None,
                   store_dir: Path | None = None, model: Any | None = None,
                   run_id: str | None = None) -> RunOutcome:
    """Top-level entry: one MCP connection, one shared budget, one run id.

    run_id lets a caller (the web API) hand out the id before the run starts.
    """
    toolset = build_mcp_toolset(db_path, store_dir)
    team = Team(toolset, model=model)
    state = TicketState(run_id=run_id or uuid.uuid4().hex[:12], run_label=run_label, ticket_id=ticket_id)
    deps = TeamDeps(agent=start_agent, depth=0, parent=None, state=state)
    async with toolset:
        return await team.run_agent(start_agent, prompt, deps)


def limits_as_dict() -> dict[str, Any]:
    return asdict(LIMITS)
