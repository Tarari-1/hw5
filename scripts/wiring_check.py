"""Connectivity proof without an LLM.

Builds the real team (real MCP stdio connection, real filtered toolsets, real
delegate tools) but swaps the model for a FunctionModel stub that records the
tool list each agent would send to the model and then stops. No model call is
made and nothing is written to the audit trail.

Usage: .venv/bin/python scripts/wiring_check.py <scratch_db> <scratch_store_dir>
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pydantic_ai.messages import ModelResponse  # noqa: E402
from pydantic_ai.models.function import AgentInfo, FunctionModel  # noqa: E402

from backend.agents import AGENT_NAMES, TOOL_SCOPES, Team, build_mcp_toolset  # noqa: E402
from backend.models import TeamDeps, TicketState  # noqa: E402


class _Captured(Exception):
    pass


async def main(db: Path, store: Path) -> int:
    seen: dict[str, list[str]] = {}

    def stub(messages, info: AgentInfo) -> ModelResponse:
        seen["_last"] = [t.name for t in info.function_tools]
        raise _Captured

    toolset = build_mcp_toolset(db, store)
    team = Team(toolset, model=FunctionModel(stub, model_name="stub-no-llm"))
    links = 0
    async with toolset:
        all_mcp = sorted(t.name for t in (await toolset.client.list_tools()))
        print(f"MCP server tools ({len(all_mcp)}): {', '.join(all_mcp)}\n")
        for name in AGENT_NAMES:
            agent = team.agents[name]
            deps = TeamDeps(agent=name, depth=0, parent=None,
                            state=TicketState(run_id="nollm", run_label="problem-5-wiring-test", ticket_id=None))
            try:
                with agent.override(model=FunctionModel(stub, model_name="stub-no-llm")):
                    await agent.run("list tools", deps=deps)
            except _Captured:
                pass
            tools = seen["_last"]
            delegates = sorted(t for t in tools if t.startswith("delegate_to_"))
            mcp_tools = sorted(t for t in tools if not t.startswith("delegate_to_"))
            links += len(delegates)
            assert set(mcp_tools) == TOOL_SCOPES[name], name
            print(f"[{name}] output_type={agent.output_type.__name__}")
            print(f"  delegate tools ({len(delegates)}): {', '.join(delegates)}")
            print(f"  MCP tools ({len(mcp_tools)}): {', '.join(mcp_tools)}")
            hidden = sorted(set(all_mcp) - set(mcp_tools))
            print(f"  MCP tools hidden from this agent ({len(hidden)}): {', '.join(hidden)}\n")
    print(f"Directed delegation links: {links} (5 agents x 4 others)")
    print("Same model object shared by all five agents:",
          len({id(a.model) for a in team.agents.values()}) == 1)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(Path(sys.argv[1]), Path(sys.argv[2]))))
