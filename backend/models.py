"""Data types for the Campus Customs agent team.

- Pydantic output types the agents must return (SpecialistReport, BossDecision).
- RunOutcome, what the team runner hands back (including clean "stopped: ..." results).
- TeamDeps / TicketState, the per-run dependencies and the state shared by every
  agent working on one ticket (delegation count, loop protection, stop flag).
- AuditEntry, one line of output/audit_trail.json.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, Field

AgentName = Literal["boss", "inventory", "accounting", "facilities", "customer_service"]
AGENT_NAMES: tuple[AgentName, ...] = ("boss", "inventory", "accounting", "facilities", "customer_service")


# --- agent outputs ---------------------------------------------------------------


class Finding(BaseModel):
    """One fact, with the tool that produced it. Numbers must come from that tool."""

    fact: str = Field(description="One fact in plain words, quoting values exactly as the tool returned them.")
    source_tool: str = Field(description="The MCP tool (or delegate_to_* tool) whose result this fact came from.")


class RecommendedAction(BaseModel):
    action: str = Field(description="What should happen next, concretely.")
    owner: AgentName | Literal["human"] = Field(description="Who should do it.")
    needs_human_approval: bool = Field(description="True for any payment, purchase order or outbound message.")


class SpecialistReport(BaseModel):
    """What Inventory, Accounting, Facilities and Customer Service return."""

    agent: AgentName
    status: Literal["complete", "needs_info", "blocked"] = Field(
        description="complete = task answered; needs_info = missing data; blocked = a shop rule prevents it."
    )
    summary: str = Field(description="Two to four sentences answering the task.")
    findings: list[Finding] = Field(default_factory=list)
    recommended_actions: list[RecommendedAction] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    proposal_ids: list[str] = Field(default_factory=list, description="Ids returned by propose_* tools, if any.")
    draft_ids: list[str] = Field(default_factory=list, description="Ids returned by save_customer_draft, if any.")


class DecisionAction(BaseModel):
    description: str
    owner: AgentName | Literal["human"]
    state: Literal["taken", "proposed"] = Field(
        description="taken = a tool already did it (e.g. draft saved, proposal created); proposed = still to do."
    )
    needs_human_approval: bool


class BossDecision(BaseModel):
    """What the Boss returns for a ticket (or for any task given to the Boss)."""

    ticket_id: int | None = Field(description="The ticket worked on, or null if the task was not a ticket.")
    worked_on_by: list[AgentName] = Field(description="Every agent that contributed, including boss.")
    final_decision: str = Field(description="The decision in two to five sentences, with the key numbers and their sources.")
    findings: list[Finding] = Field(default_factory=list)
    actions: list[DecisionAction] = Field(default_factory=list)
    human_approval_needed: bool
    approval_items: list[str] = Field(default_factory=list, description="Proposal ids waiting for a human.")
    ticket_status_set: Literal["resolved", "declined"] | None = Field(
        default=None, description="Set only if resolve_ticket was actually called."
    )


class RunOutcome(BaseModel):
    """Returned by every agent run, including runs that were stopped by a limit."""

    agent: AgentName
    status: str = Field(description="'ok' or 'stopped: <reason>'.")
    output: dict[str, Any] | None = None
    run_id: str
    depth: int
    usage: dict[str, int] = Field(default_factory=dict)


# --- runtime state -----------------------------------------------------------------


@dataclass
class TicketState:
    """Shared by every agent run under one top-level run (one budget, one ticket)."""

    run_id: str
    run_label: str
    ticket_id: int | None
    delegations: int = 0
    delegation_signatures: set[tuple[str, str, str]] = field(default_factory=set)
    stopped: str | None = None


@dataclass
class TeamDeps:
    """Per-agent-run dependencies (a child run gets its own, sharing `state`)."""

    agent: AgentName
    depth: int
    parent: AgentName | None
    state: TicketState
    seen_tool_calls: set[tuple[str, str]] = field(default_factory=set)


# --- audit -------------------------------------------------------------------------

StepType = Literal["model_request", "tool_call", "tool_result", "delegation", "final_answer", "limit_stop", "error", "note"]


class AuditEntry(BaseModel):
    ts: str
    run_label: str
    run_id: str
    ticket_id: int | None
    agent: AgentName | None  # None only for operator "note" entries
    depth: int | None
    parent_agent: AgentName | None
    step: StepType
    name: str | None = None
    arguments: dict[str, Any] | None = None
    result_summary: str | None = None
    usage: dict[str, int] | None = None
    stop_reason: str | None = None
    model: str
