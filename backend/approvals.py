"""The human approval path for payment and purchase-order proposals.

This is a plain backend function, used by scripts/approve.py. It is NOT an MCP
tool and no agent is given it, so an agent can propose a payment but can never
approve one. pay_approved (on the MCP server) only executes proposals whose
approval_path equals stores.HUMAN_APPROVAL_PATH, which only this module writes.
The approver's name becomes payments.approved_by when the payment executes.
"""

from __future__ import annotations

import re
from typing import Any

from mcp_server import stores

# A person's name: 1 to 60 characters after trimming, starting with a letter.
_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z .'-]{0,59}$")


def decide(proposal_id: str, approver: str, approve: bool = True, reason: str | None = None) -> dict[str, Any]:
    """Approve (or reject) one pending proposal on behalf of a named human."""
    approver = (approver or "").strip()
    if not _NAME_RE.match(approver):
        return {"ok": False, "reason": "approver must be a person's name, 1 to 60 characters (letters, spaces, . ' -)."}
    with stores.locked(stores.APPROVALS) as records:
        match = [r for r in records if r.get("id") == proposal_id]
        if not match:
            return {"ok": False, "reason": f"No proposal with id {proposal_id!r}."}
        p = match[0]
        if p.get("status") != "pending":
            return {"ok": False, "reason": f"{proposal_id} is {p.get('status')!r}, not 'pending'."}
        p.update(
            status="approved" if approve else "rejected",
            approved_by=approver if approve else None,
            rejected_by=None if approve else approver,
            approval_path=stores.HUMAN_APPROVAL_PATH if approve else None,
            decided_at=stores.now_utc(),
        )
        if not approve and reason:
            p["rejection_reason"] = reason
        return {"ok": True, "proposal": dict(p)}


def revert_to_pending(proposal_id: str, failure_reason: str, attempted_by: str) -> dict[str, Any]:
    """Undo an approval whose payment was refused, so no approved-but-unpaid proposal lingers.

    Only an 'approved' proposal is reverted (an executed one is never touched). The
    refusal is kept in `failures` so the human can see why the payment did not go through.
    """
    with stores.locked(stores.APPROVALS) as records:
        match = [r for r in records if r.get("id") == proposal_id]
        if not match or match[0].get("status") != "approved":
            return {"ok": False, "reason": f"{proposal_id} is not in 'approved' state; nothing reverted."}
        p = match[0]
        p.setdefault("failures", []).append(
            {"at": stores.now_utc(), "attempted_by": attempted_by, "reason": failure_reason})
        p.update(status="pending", approved_by=None, approval_path=None, decided_at=None)
        return {"ok": True, "proposal": dict(p)}


def pending() -> list[dict[str, Any]]:
    return [r for r in stores.read_all(stores.APPROVALS) if r.get("status") == "pending"]
