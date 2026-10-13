"""No-LLM check that limits stop cleanly with "stopped: <reason>".

A FunctionModel stub plays every agent: it always delegates down a chain
(boss -> inventory -> accounting -> facilities -> customer_service) and, once a
delegation returns, gives a final answer. Audit entries go to a scratch file
(AUDIT_TRAIL_PATH), not output/audit_trail.json, since no real model is called.

  depth   the 4th-level delegation is refused: max delegation depth 3
  usage   request_limit=2: the run stops with "stopped: usage limit ..."

Usage: AUDIT_TRAIL_PATH=<scratch.json> .venv/bin/python scripts/limits_check.py <scratch_db> <store>
"""

import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
assert "AUDIT_TRAIL_PATH" in os.environ, "point AUDIT_TRAIL_PATH at a scratch file"

from pydantic_ai.messages import ModelResponse, ToolCallPart, ToolReturnPart  # noqa: E402
from pydantic_ai.models.function import AgentInfo, FunctionModel  # noqa: E402

import backend.agents as A  # noqa: E402
from backend.models import TeamDeps, TicketState  # noqa: E402

CHAIN = ["boss", "inventory", "accounting", "facilities", "customer_service"]


def stub(messages, info: AgentInfo) -> ModelResponse:
    last = messages[-1].parts
    returned = [p for p in last if isinstance(p, ToolReturnPart)]
    tools = {t.name for t in info.function_tools}
    me = next(a for a in CHAIN if f"delegate_to_{a}" not in tools)
    if not returned:
        nxt = CHAIN[(CHAIN.index(me) + 1) % len(CHAIN)]
        return ModelResponse(parts=[ToolCallPart(f"delegate_to_{nxt}", {"task": f"chain step from {me}"})])
    child = returned[0].content
    status = child.get("status") if isinstance(child, dict) else str(child)
    out = ({"ticket_id": None, "worked_on_by": ["boss"], "final_decision": f"child said: {status}",
            "human_approval_needed": False} if me == "boss" else
           {"agent": me, "status": "complete", "summary": f"child said: {status}"})
    return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, out)])


async def run(limits: A.TeamLimits, label: str, db: Path, store: Path) -> None:
    ts = A.build_mcp_toolset(db, store)
    team = A.Team(ts, model=FunctionModel(stub, model_name="stub-no-llm"), limits=limits)
    deps = TeamDeps(agent="boss", depth=0, parent=None,
                    state=TicketState(run_id=label, run_label="problem-5-wiring-test", ticket_id=None))
    async with ts:
        out = await team.run_agent("boss", "start", deps)
    print(f"[{label}] top-level status: {out.status}; output: {json.dumps(out.output)}")
    entries = [e for e in json.loads(Path(os.environ["AUDIT_TRAIL_PATH"]).read_text()) if e["run_id"] == label]
    for e in entries:
        if e["step"] in ("delegation", "limit_stop", "final_answer", "error"):
            print(f"   {e['agent']:<16} depth={e['depth']} {e['step']:<13} {e['name'] or ''} {e['stop_reason'] or ''}")


async def main(db: Path, store: Path) -> int:
    await run(A.TeamLimits(), "depth", db, store)
    await run(A.TeamLimits(request_limit=2), "usage", db, store)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(Path(sys.argv[1]), Path(sys.argv[2]))))
