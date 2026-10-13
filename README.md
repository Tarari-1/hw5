# Campus Customs: an agent team that runs a shop's back desk

Homework 5 (AI Foundations). Five PydanticAI agents (Boss, Inventory, Accounting,
Facilities, Customer Service) work the open tickets of a small campus print shop.
They reach the shop's SQLite database only through one MCP server (FastMCP, 19
tools). Agents can only *propose* payments and purchase orders; a human approves
them in a React dashboard, and only then does money move. Every agent step goes
to an append-only audit trail. The model is pinned to **gpt-6-luna** through the
Portkey gateway.

## Layout

```
AI_prompts.md        every prompt given to the coding assistant, problem by problem
requirements.txt     Python dependencies
.env.example         placeholder for PORTKEY_API_KEY (copy to .env)
.mcp.json, mcp.json  MCP server config (see below)
data/                campus_customs.db (original) and campus_customs_new.db (working copy)
mcp_server/          server.py (the 19 MCP tools), stores.py, README.md
backend/             main.py (FastAPI), agents.py, models.py, audit.py, approvals.py,
                     demo_runner.py, prompts/ (one prompt file per agent)
frontend/            React + Vite + TypeScript dashboard ("The Back Desk")
scripts/             reset_db.py, approve.py, check_models.py and the test scripts
output/              harness.md, design.md, desk_tickets.html, resolved_tickets.json,
                     resolved_board.html, audit_trail.json, mcp_smoke.json, screenshots
```

`.mcp.json` is the file Claude Code reads; `mcp.json` is an identical, visible copy.

## Prerequisites

- Python 3.13 (tested with 3.13.15)
- Node.js 24 and npm 11 (tested with Node 24.20 and npm 11.19)
- A Portkey API key with access to gpt-6-luna (only needed to run the agents)

## Setup

```bash
git clone https://github.com/Tarari-1/hw5.git
cd hw5
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # then set PORTKEY_API_KEY in .env
cd frontend && npm install && cd ..
```

The interpreter path in `.mcp.json` is `.venv/bin/python`, so create the virtual
environment at the repo root as shown.

## The two databases

- `data/campus_customs.db` is the **original**. It is never modified; nothing
  writes to it.
- `data/campus_customs_new.db` is the **working copy**, where runs read and write.
  The published working copy is the state after the author's run (see below).

To start a clean run, copy the original over the working copy:

```bash
cp data/campus_customs.db data/campus_customs_new.db
```

`python scripts/reset_db.py --confirm` and `POST /api/reset` with `{"confirm": true}`
(the dashboard's "Clear the desk…" button) do the same, verify the checksum, and
also clear the three runtime stores (approvals, drafts board, ticket resolutions).
The stores are created on first use and aren't in the repo. The audit trail is
never wiped; a reset only appends a note to it.

## Running it

**MCP server.** `python mcp_server/server.py` runs it standalone over stdio for
MCP clients such as Claude Code, which starts it through `.mcp.json`. The backend
starts its own copy per request, so the dashboard doesn't need a separate MCP
terminal.

**Backend** (FastAPI, http://localhost:8000; with the virtual environment active):

```bash
cd backend && uvicorn main:app --reload --port 8000
```

**Dashboard** (in a second terminal):

```bash
cd frontend && npm run dev
```

Then open http://localhost:5173.

## A full three-ticket run

1. Reset first: click "Clear the desk…" in the dashboard (or use one of the reset
   commands above). All three tickets show as open and checking shows $3,400.00.
2. Select ticket 101 and click "Hand ticket 101 to the team". Watch the agents on
   the floor; the run ends with the Boss's memo. Do the same for 102, then 103,
   one at a time.
3. When a payment or purchase order is proposed, it appears under "Needs a
   signature". **A human clicks Approve, types their name and confirms**; agents
   only propose. Only then does `pay_approved` move money, and it refuses if cash
   is short. Rejecting is also allowed.

Each run uses real model calls (and tokens). `/api/health` shows the runner in
use; it must be `main.default_runner` for a real run.

## Model rule

Every agent uses only **gpt-6-luna**, through Portkey with `PORTKEY_API_KEY`. The
name is defined once (`MODEL_NAME` in `backend/agents.py`).
`python scripts/check_models.py` fails if any other model name appears in the
project.

## The author's run

On the author's run: ticket 101 was **resolved**, 102 was **resolved** (after a
human approved the $2,400 rent payment), and 103 was **declined** by the Boss.
Checking went from **$3,400.00 to $1,000.00**. That is one recorded run, not a
guarantee; the agents can choose differently on another run. Details, including
where the agents didn't follow their prompts, are in `output/harness.md` ("Full
run results") and `output/resolved_tickets.json`.

The approver's name in the published outputs and working database was replaced
by "[human approver]".

## More

- `output/harness.md`: database study, the 19 MCP tools, the agents, the API
  routes, safety (what is enforced in code and what only in prompts), and the
  full run results.
- `output/design.md`: the dashboard's design and accessibility choices.
