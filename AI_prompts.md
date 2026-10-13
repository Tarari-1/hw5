# AI Prompts Log

A running log of the prompts given to Claude for Homework 5.

Each problem section records the prompt(s) typed, and — where a first prompt
wasn't enough — the follow-up plus a note on what was missing.

## Setup

**2026-10-08**

1. `Today we are working on Homework 5`
2. `I'm going to tell you the instructions for Homework 5. Just chill!!`

---

## Problem 1 — Vibe coder prompts

**Prompt 1:**

> Problem 1: Vibe coder prompts
>
> Create AI_prompts.md. This will be a log of what I typed into our chats. You should keep it updated as we work on this project. There should be one section for each problem. Each section must include:
>
> * the problem number & title
> * at least one prompt I typed
> * one follow-up prompt if I needed it (and one sentence on what was lacking after the first prompt)

**Follow-up:** _none needed_

---

## Problem 2 — Study the Campus Customs database

**Prompt 1:**

> Problem 2: Study the Campus Customs database
>
> What I need: get to know the shop's database before we build any agents. Go through each table and understand what every field holds. Make a working copy of the database that later problems can change freely, and leave the original alone so we can always start over. Look at the three tickets that are currently open and work out how each one connects to the rest of the data. Then start a harness document that records what you learned, table by table, including a quick note on why each table will matter to the agents. I'll keep adding to that document in later problems.
>
> First, append this prompt to AI_prompts.md verbatim, as usual.
>
> Rules:
> - Treat data/campus_customs.db as read-only. Open it with sqlite3 in read-only mode (file:...?mode=ro). Record its SHA-256 before and after and show both.
> - Save the working copy as data/campus_customs_new.db, a byte-for-byte copy. Show that its checksum matches the original.
> - Don't write any agent code yet. This problem is study and documentation only.
> - Everything in output/harness.md must come from the database itself, not guesses. If something about a field is unclear (units, status values, what a foreign key points to), say it's unclear instead of inventing a meaning.
>
> Do this:
> 1. List every table with its row count and its full schema (column names, types, primary keys, foreign keys, any unique or check constraints).
> 2. For each table, show 3 sample rows. For columns that look like categories or statuses (ticket status, ticket type, invoice status, payment status, and so on), list the distinct values with counts.
> 3. Read desk.date_today and show it. Note what "overdue" means for invoices and leases, based on the actual columns.
> 4. Find the three open tickets. For each, show the full ticket row. Then trace every link: the SKUs, sizes, vendors, invoices, leases, payments and cash accounts it touches, with the actual linked rows pulled by query. Show how the ticket's own fields point to those rows, and say if a link is only implied by free text in the ticket and not by a real key.
> 5. For each ticket, note what the data already shows, such as stock versus requested quantity, vendor lead time, whether that vendor has an open unpaid invoice, and the cash balance versus the amount involved. Don't resolve any ticket and don't change any data.
> 6. Write output/harness.md with:
>    - A short intro saying what this file is, that it will be extended in later problems, and the shop's "today" date.
>    - A "Database tables" section. For each table, give the field list (with types) and one line on why it matters for the agents.
>    - A short "How the three open tickets link to the data" section with one table or short paragraph per ticket.
>    - A "Things to watch" section with only data quirks you actually found (nulls, inconsistent formats, columns that duplicate each other, links that exist only in text).
>
> Report back with raw output, not a summary: the checksum lines, the table names with row counts, the schema dump, the three ticket rows, and the linked rows you pulled for each. Then show the final harness.md.

**Follow-up:** _none needed_

---

## Problem 3 — Build the MCP server

**Prompt 1:**

> Problem 3: Build the MCP server
>
> First, append this prompt to AI_prompts.md verbatim, as usual.
>
> What I need: the shop's agents will all work through one MCP server, so build its first version. Put it in mcp_server/server.py using FastMCP, pointed at data/campus_customs_new.db. Start with three tools, each one that a specific open ticket (101, 102 or 103) clearly needs. I'll add more tools in later problems. This problem is about writing and documenting the server. You don't need to start it or connect anything to it.
>
> The three tools (use these names):
> 1. check_stock(sku, size): returns the row from inventory for that SKU and size (name, qty, location), plus qty for every size of that SKU so the caller can see the alternatives. This is for ticket 101 (the S tee is at 0) and also helps with ticket 103.
> 2. get_lease(lease_id): returns the lease row, plus days_until_due and an is_overdue flag, calculated from desk.date_today, never from the computer's clock. Also return the checking balance from cash_accounts so the caller can see whether rent is covered. This is for ticket 102.
> 3. get_pricing(sku): returns unit_cost and list_price from pricing, plus margin_pct at list price. This is for ticket 103's discount decision.
>
> Rules for all three:
> - Read-only. Open the database in read-only mode (file:...?mode=ro) and never write, so nothing here can change the data.
> - Take the database path from one constant at the top of the file, set to the working copy data/campus_customs_new.db, resolved relative to the project root so it works from any directory. Never point at campus_customs.db.
> - Never invent data. If a SKU, size or lease doesn't exist, return a clear not-found result (for example {"found": false, "error": "..."}) instead of guessing or defaulting. Keep null (missing) and zero (a real 0) distinct, since an out-of-stock size is qty 0, not "unknown".
> - Validate inputs (non-empty strings, ids that are integers) and use parameterized SQL only, never string-built SQL.
> - Clear type hints and a docstring on each tool saying what it returns and which table(s) it reads, because the agents will read these as the tool descriptions.
> - Add fastmcp to requirements.txt (create the file if it doesn't exist yet).
>
> Documentation:
> - Append to output/harness.md. Don't delete or rewrite anything already in it. Add a section "MCP tools" listing each of the three tools with: the table(s) it reads, which ticket it helps unlock, and one sentence on why that tool is the right one for that ticket, tied to the real data (for example, naming the actual SKU, size or lease from that ticket). Avoid vague lines such as "reads inventory".
> - Create mcp_server/README.md, short: what the MCP server is for, which database file it uses, and the three tools it has with one line each.
>
> Checks (don't start the MCP server, but do prove the functions are correct):
> - Import the module and call each tool function directly against the working copy for the real cases: check_stock("CC-TEE-WHITE","S"), check_stock("CC-HOOD-NAVY","M"), get_lease(1), get_pricing("CC-HOOD-NAVY"), plus a not-found case for each tool. Show the raw returned values.
> - Show that data/campus_customs.db and data/campus_customs_new.db checksums are unchanged from before (both should still be 23686a90d698f7fa6f901a3f0a9774db9cbb31e13151c9e5717275f3321f360a).
> - Show the final server.py, mcp_server/README.md, and the new "MCP tools" section of harness.md.

**Follow-up:** _none needed_

---

## Problem 4 — Add the MCP server to vibe coder and test each tool, part A

**Prompt 1:**

> Problem 4: Add the MCP server to vibe coder and test each tool, part A
>
> First, append this prompt to AI_prompts.md verbatim, as usual.
>
> What I need: make my MCP server available to you inside this project, so that in a fresh session you can call its three tools yourself. Register the server in .mcp.json at the project root (the project-scoped MCP config Claude Code reads), pointing at mcp_server/server.py.
>
> Rules:
> - Use a relative path to server.py and a portable command. If the project has a virtualenv, use its relative interpreter path (for example .venv/bin/python). Otherwise use python3. Don't put any absolute /Users/... path in the file, because this repo will be public.
> - No secrets in .mcp.json. This server needs none.
> - Make sure the interpreter that .mcp.json uses actually has fastmcp installed. Show the command you used to confirm.
> - Don't change the server's tools or the database. Show that both database checksums are still 23686a90d698f7fa6f901a3f0a9774db9cbb31e13151c9e5717275f3321f360a.
>
> Do this:
> 1. Write .mcp.json.
> 2. Confirm the server starts and registers using the real client path, not only by importing the module: run `claude mcp list` (or `claude mcp get <name>`) and show the raw output, including whether it says the server is connected or needs approval. If the CLI isn't available, start the server over stdio and send an MCP initialize plus tools/list request, and show the raw tool list.
> 3. Show the final .mcp.json.
> 4. Tell me exactly what I need to do next in the app to approve the project server and start a fresh session so the three tools are callable (for example approving the project MCP server, then restarting in this folder). Don't do any smoke testing yet.

**Follow-up:**

> this is what it pastes in the termianl when I tried to do number 2
>
> _(attached: screenshot of the Claude Code CLI first-run "Choose the text style" theme screen)_

> yes  _(approving the `.claude/settings.local.json` pre-approval option)_

_What was lacking after the first prompt:_ my approval steps assumed the
bundled `claude` CLI was already set up, but running it for the first time
opens the CLI's own setup screens before any MCP approval prompt appears.

> Let's try this again  _(fresh session in the project folder after approving the server)_

---

## Problem 4 — Add the MCP server to vibe coder and test each tool, part B

**Prompt 1:**

> Problem 4: Add the MCP server to vibe coder and test each tool, part B
>
> First, append this prompt to AI_prompts.md verbatim, as usual.
>
> What I need: prove that you can call my three MCP tools through the real MCP connection, and save the evidence. Ask yourself the three requests below as if I had typed them, and answer each by actually calling the matching tool from the shop MCP server.
>
> The three requests:
> 1. "Do we have any Classic Bulldog Tees in white, size S, in stock? What about other sizes?"
> 2. "When is the Chapel Street shop rent due, and do we have enough in checking to cover it?"
> 3. "What does a navy Basic Hoodie cost us, what do we list it for, and what's the margin?"
>
> Strict rules:
> - Every result must come from a real MCP tool call made through the connected server. Don't call the Python functions directly, don't read the database and then write what the tool "would" return, and don't type any tool output from memory. If the MCP tools aren't available in this session, stop and tell me, and don't substitute anything.
> - Before the calls, list the MCP tools you can see, with their exact names, and show that list.
> - For each request, record the exact tool name that was called and the exact arguments you passed.
> - After all three calls, query data/campus_customs_new.db separately (read-only) for the same facts, and compare field by field. Set "matches_database" to true only if every value in the tool output equals the database.
> - Don't write to either database. Show that both checksums are still 23686a90d698f7fa6f901a3f0a9774db9cbb31e13151c9e5717275f3321f360a.
>
> Write output/mcp_smoke.json as valid JSON: an object with a "server" name, "database": "data/campus_customs_new.db", and a "tests" array with exactly three entries. Each entry has:
> - "ticket": 101, 102 or 103
> - "prompt": the request text above, verbatim
> - "tool": the tool name that was called
> - "arguments": the arguments passed
> - "tool_output": the raw output the tool returned
> - "database_check": the query you ran and the values it returned
> - "matches_database": true or false
>
> Then show me: the tool list, the raw output of each tool call as it came back, the database comparison, and the final output/mcp_smoke.json (validate it with a JSON parser and show that it parsed).

**Follow-up:** _none needed_

---

## Problem 5 — Build the agent team and grow the MCP tools

**Prompt 1:**

> Problem 5: Build the agent team and grow the MCP tools
>
> First, append this prompt to AI_prompts.md verbatim, as usual.
>
> What I need: the working team that will run the shop. Five PydanticAI agents (Boss, Inventory, Accounting, Facilities, Customer Service), each with its own prompt file, a typed output, and a loop. Any agent can hand work to any other agent, so every agent gets a delegation tool for each of the other four. Every fact about the shop must come through the MCP server, so extend that server with whatever extra tools the agents need to work the open tickets (101, 102, 103). Every step the agents take must be written to an audit file. You won't resolve the tickets in this problem. This problem is building, wiring and documenting the team, and proving it is wired correctly.
>
> Setup checks first (create only what's missing, don't overwrite):
> - homework-5 needs .env with PORTKEY_API_KEY. If it's missing, copy that one value file-to-file from homework-4/.env without printing it. Make sure .env is in .gitignore, and that .env.example holds placeholders only.
> - requirements.txt must include pydantic-ai, fastmcp, fastapi, uvicorn and anything else you actually import.
>
> Model rule (graded, strict): every agent uses only gpt-6-luna through Portkey with PORTKEY_API_KEY. Define the model name once, in one constant, and build one shared model object that all five agents use. Mirror the gateway wiring that homework-4/backend/agent.py already uses (read it, don't modify it), but pin the model. No other model name may appear in code, config, docs, comments or logs. Add scripts/check_models.py that greps the project (excluding .env and data/) for other model-name patterns (gpt-, claude, gemini, etc.) and fails if it finds anything besides gpt-6-luna. Run it and show the output.
>
> Layout:
> - backend/prompts/boss.md, inventory.md, accounting.md, facilities.md, customer_service.md
> - backend/models.py for all data types
> - backend/agents.py (or one file per agent under backend/, your choice) with the five agents, the shared model, and the delegation wiring
> - backend/audit.py for the audit trail writer
> - mcp_server/server.py extended, mcp_server/README.md updated
>
> Agents, in plain terms:
> - Boss: reads a ticket, decides who should work on it, and makes the final call. Boss never moves money itself.
> - Inventory: stock by SKU and size, spots shortfalls, works out which vendor can restock and how long that takes.
> - Accounting: cash, invoices, margins. Prepares payments and purchase orders for human approval.
> - Facilities: the shop space: leases and rent.
> - Customer Service: drafts messages to customers. Drafts only.
>
> Prompts: write each in your own words, and make them detailed rather than generic. Each prompt should cover that agent's scope, what it should and should not do, which tools it has and when to use each one, which shop rules apply to it, when to ask which other agent for help (and when not to), what a good final answer looks like, and the rule to never state a number that didn't come from a tool. Shop rules to build in where they apply:
> - desk.date_today is "today", and decides what is overdue.
> - Vendor lead times come from the vendors table.
> - A vendor will not ship new product while it has an open unpaid invoice.
> - Any payment needs human approval.
> - If cash is insufficient the payment must be refused, and no balance may go negative.
> - Cash only goes out, because revenue isn't modelled.
> - Never email customers or contact real vendors. Drafts stay on the board.
> - Discount decisions must respect cost from pricing (never below cost) and be explained with the margin.
>
> Typed outputs (backend/models.py): define clear Pydantic models, for example a report each specialist returns (summary, findings with the source tool for each, recommended actions, open questions) and a decision the Boss returns (ticket id, who worked on it, final decision, actions taken or proposed, whether human approval is needed). Use them as each agent's output_type.
>
> Delegation (full connectivity):
> - Each agent has delegate_to_<other agent> tools for all four others (20 directed links in total). A delegation runs the other agent with a clear task string and returns its typed report.
> - Pass the parent run's usage into the child run, so one shared budget covers a whole ticket.
> - Limits (put them in one config block, and use sensible defaults): maximum delegation depth (3), maximum total delegations per ticket, maximum model requests and tool calls per ticket via UsageLimits, a per-run wall-clock timeout, a cap on output tokens per model request, and loop protection that stops an agent repeating an identical delegation or tool call. When a limit is hit, stop cleanly and return a clear "stopped: <reason>" result. Don't crash or retry forever.
>
> MCP rules:
> - Agents reach the shop only through the MCP server (use the PydanticAI MCP client toolset for the installed version, and check its actual API rather than assuming). No direct sqlite access from any agent code, and no second tools layer.
> - Keep the existing three tools. Add the tools the agents need, with clear names. Suggested set (adjust if you find a better fit, and justify any change in harness.md): list_open_tickets, get_ticket, get_today, list_vendors, get_vendor_open_invoices, get_invoice, get_cash_balance, list_payments, propose_payment, propose_purchase_order, pay_approved, save_customer_draft, resolve_ticket.
> - Reads are read-only (mode=ro).
> - Human approval, enforced in code, not only in prompts. Agents can only PROPOSE a payment or purchase order. A proposal creates a pending record in a separate approvals store (a JSON file under data/, not a schema change to the shop database) and moves no money. pay_approved(proposal_id) executes only if that record's status is "approved" and was set by a human approval path. Provide that approval path as a plain backend function (and a small CLI, scripts/approve.py) that is NOT exposed as an MCP tool and not reachable from any agent. The human's name goes into payments.approved_by.
> - pay_approved must refuse when cash is insufficient (no negative balance), when the amount doesn't match the proposal, when the proposal was already executed (no double pay), and when the target invoice isn't open. On success it writes the payments row, lowers cash_accounts.balance, and updates the relevant table (invoice status to paid; for rent, advance the lease's next_due by one month and say clearly in the harness that this was a modelling choice).
> - propose_purchase_order must be refused in code if that vendor currently has any open unpaid invoice, and it must compute the expected arrival date from today plus the vendor's lead_days. A purchase order proposal doesn't change inventory.
> - save_customer_draft stores a draft on the board (a JSON file under data/ or output/, not sent anywhere). No tool anywhere may send email or contact anyone.
> - resolve_ticket sets the ticket status and stores a short resolution note. Only the Boss's prompt should use it, but note honestly in the harness that this is a prompt-level restriction unless you also restrict it in code, and if you can scope it per agent in code, do.
> - Inputs are validated, SQL is parameterized, "not found" is explicit, null and zero stay distinct, and nothing is invented.
> - For every write tool, test on a scratch COPY of the database, never on data/campus_customs_new.db. data/campus_customs_new.db and data/campus_customs.db must remain byte-identical to the original (checksum 23686a90d698f7fa6f901a3f0a9774db9cbb31e13151c9e5717275f3321f360a), because the full run is a later problem.
>
> Audit trail (output/audit_trail.json):
> - Appends only. Never wipe or recreate it on a run. Keep it valid JSON (an array), write safely (lock, temp file, fsync, os.replace), and if the file is corrupt, rename it aside and never delete it, as in my HW4 audit writer.
> - One entry per agent-loop step: timestamp, run_id, ticket_id, which agent, delegation depth and parent agent, step type (model request, tool call, tool result, delegation, final answer, limit stop, error), tool or delegate name, arguments, a short result summary, token usage so far when available, and stop reason when it ends. Instrument with the PydanticAI iteration API and the MCP tool-call hook so every step is captured, including MCP tool calls.
> - Redact secrets and anything that looks like an API key. Don't log the raw prompt text.
> - Entries from tests in this problem must be labeled run_label "problem-5-wiring-test" so they can be told apart from the real run later.
>
> Verify (no ticket resolution):
> 1. Connectivity proof without an LLM: build all five agents and print, for each, the list of its tools, showing 4 delegate tools each and the MCP tools it can see. State the number of directed delegation links.
> 2. Run scripts/check_models.py and show the raw output.
> 3. One minimal live call per agent through Portkey with gpt-6-luna (a trivial prompt, such as "state your role and list your tools"), no ticket, to prove the model call works. Keep this cheap. Show the raw outputs, and the raw error if any call fails.
> 4. One live delegation round trip, cheap: ask Boss only "ask Inventory to report the stock of CC-TEE-WHITE in size S" and show the final answer plus the audit entries produced. Confirm the answer matches the database (qty 0).
> 5. Write-tool tests on a scratch copy of the database: show propose_payment then pay_approved refused (not approved), then approve via the human path and pay_approved succeeds, a second pay_approved refused (double pay), a payment larger than cash refused, and propose_purchase_order for vendor 1 refused (open invoice 501) while vendor 2 isn't refused. Show raw results and the scratch database before and after.
> 6. Show both checksums of data/campus_customs.db and data/campus_customs_new.db, still equal to the original.
> 7. Show the audit file's entry count and the first few entries, and run the append test: run twice and show that the count only grew.
>
> Docs:
> - Append to output/harness.md (don't delete or rewrite anything already there): a section "Agents" (each agent: role, tools it can call, who it can delegate to, output type); a section "MCP tools" (every tool, including the three from Problem 3 and the new ones, with the table or store each tool uses, whether it reads or writes, and which ticket it helps); and a section "Safety" with the guardrails a real business would want when agents touch real customers and real money (human approval, refusal on insufficient cash, no outbound contact, the vendor-invoice hold, audit trail, secrets and personal-data handling, idempotency, spending caps), clearly separating what's enforced in code from what's only in the prompts, plus the limits that keep token use in check (the limit config above, the shared usage budget, the single model).
> - Update mcp_server/README.md so the tool list matches exactly what the server has now.
>
> Report back with raw output for each verification step above, the final list of MCP tools with their names, and the final text of each of the five prompt files.

**Follow-up:**

> Redact in place, but keep the audit trail's integrity: replace only that one dated model ID string with "gpt-6-luna" using the safe locked write, keeping every entry. Then append a new audit entry (run_label "problem-5-wiring-test", step type "note") saying exactly what was edited, which entry it was, and why (a dated gateway snapshot ID of gpt-6-luna was normalized so the model check passes). Also make the audit writer itself normalize any dated gpt-6-luna snapshot ID to "gpt-6-luna" before writing, so this can't recur in the real run. Mention the one-time edit in harness.md's Safety section as a known exception to append-only. Then re-run check_models.py and show that it passes.

_(answer to my question about one old audit entry)_

_What was lacking after the first prompt:_ the prompt didn't say what to do when
the model gateway's own error text names a dated snapshot of the pinned model,
which ended up in an append-only log and made the model-name check fail.

---

## Problem 5 — follow-up checks

**Prompt 1:**

> Follow-up on Problem 5 (first append this prompt to AI_prompts.md verbatim). Two checks, with raw output:
>
> 1. Show that the REAL approvals store and the REAL customer-drafts store (the files the MCP server uses by default, under data/ or output/) are empty or don't exist, and that no earlier test wrote to them. If either has test content, move it out as a dated backup and leave a clean store. Show the file listing and contents before and after.
>
> 2. On a scratch copy of the database and scratch stores only, test save_customer_draft (show the saved record; nothing is sent anywhere) and resolve_ticket (show the ticket status before and after, and that an unknown ticket id is refused clearly).
>
> Finish by showing both database checksums (still 23686a90d698f7fa6f901a3f0a9774db9cbb31e13151c9e5717275f3321f360a).

**Follow-up:** _none needed_

---

## Problem 6 — Plan the three tickets

**Prompt 1:**

> Problem 6: Plan the three tickets
>
> First, append this prompt to AI_prompts.md verbatim, as usual (including the expectation text I filled in below).
>
> What I need: a planning page that records what I expect the agent team to do on each open ticket, written BEFORE any agent runs, so I can compare it with the real runs later. Build output/desk_tickets.html as one self-contained file I can double-click to open: no external requests, no CDN, no web fonts, just HTML, CSS and a little JavaScript.
>
> Do not run any agents, call any model, or open any results for this problem. This is a static page only.
>
> Page requirements:
> - Five tabs: "Ticket 101", "Ticket 102", "Ticket 103", "Cash" and "Reflection".
> - Each ticket tab shows the ticket's id, type, requester and subject. Read those four fields from the ticket rows in data/campus_customs_new.db now and write them in as static text (this page has no database access when opened).
> - Each ticket tab has an "Expected" section, filled with exactly the text I give below, and an "Actual" section that is empty for now, with a clear placeholder such as "To be filled after the agents run." Keep the Expected and Actual sections visually parallel so they can be compared side by side later.
> - In the Expected section, show three labelled parts in this order: "Who the Boss calls first and why", "Delegations I expect", and "MCP tools I expect to be used".
> - The Cash and Reflection tabs are blank except for a short "Coming in a later problem" note.
> - Use the text I supplied word for word. Don't edit, polish, shorten, reorder or add to my wording or my lists, and don't add any expectations of your own. Escape the text so it displays exactly as typed. If you notice a tool name I wrote that doesn't exist on the MCP server, don't change it: tell me in your report.
> - Give every section a stable, descriptive id (for example t101-expected, t101-actual) so a later problem can fill the Actual sections without redesigning the page.
> - Make the tabs keyboard accessible (arrow keys and visible focus), readable at phone width, with good contrast, and printable. The page should still show all content if JavaScript is disabled (for example by showing every tab's content stacked when scripting is off).
> - Keep the look clean and simple. This isn't the dashboard; design effort should be modest.
>
> My expectations (use exactly as written):
>
> TICKET 101 (customer order)
> Who Boss calls first and why: Inventory. The customer's problem is stock: the white Bulldog Tee in size S is out of stock, so Inventory should confirm the quantity, find which other sizes are available, and check the restock options and lead time.
> Delegations I expect: Boss asks Inventory for the stock position and alternative sizes. Boss then asks Customer Service to draft a reply offering a size that is in stock. I don't expect Accounting, Facilities or any specialist-to-specialist delegation, because no money needs to move.
> MCP tools I expect: get_ticket, check_stock, list_vendors, save_customer_draft, resolve_ticket
>
> TICKET 102 (rent notice)
> Who Boss calls first and why: Facilities. This is a rent notice about the shop lease, and Facilities owns the lease, the rent amount and the due date.
> Delegations I expect: Boss asks Facilities for the lease and due date. Facilities then asks Accounting to check that cash covers the rent and to propose the rent payment for human approval. I don't expect Inventory or Customer Service. The ticket should stay open until a human approves the payment.
> MCP tools I expect: get_ticket, get_lease, list_payments, get_cash_balance, propose_payment
>
> TICKET 103 (price override)
> Who Boss calls first and why: Inventory. The request is for 20 navy hoodies in size M and the shop may not have that many, so I want to know first whether the order can be filled at all before deciding on any discount.
> Delegations I expect: Boss asks Inventory for the stock position. Inventory then asks Accounting about the restock cost and whether the vendor is on hold, and Accounting also gives the cost and margin that set the discount floor. Boss then asks Customer Service to draft a holding reply that promises nothing that is not confirmed. I don't expect Facilities.
> MCP tools I expect: get_ticket, check_stock, list_vendors, get_vendor_open_invoices, get_pricing, save_customer_draft
>
> Checks:
> - Open the page in a headless browser, take a screenshot of each of the five tabs, and show them to me. Also show that it makes no network requests.
> - Show that the Expected text in the HTML matches what I pasted, character for character (a diff of the raw text against the page's text).
> - Confirm no agent or model was run, no database was changed (both checksums still 23686a90d698f7fa6f901a3f0a9774db9cbb31e13151c9e5717275f3321f360a), and no file other than output/desk_tickets.html and AI_prompts.md was changed.

**Follow-up:** _none needed_

---

## Problem 7 — Backend routes

**Prompt 1:**

> Problem 7: Backend routes
>
> First, append this prompt to AI_prompts.md verbatim, as usual.
>
> What I need: the web API that the dashboard (next problem) will call. Put it in backend/main.py with FastAPI, so that running `uvicorn main:app --reload --port 8000` from the backend/ folder starts it at http://localhost:8000. It must work when launched from backend/ (imports, and paths to data/, output/, the MCP server file and the project-root .env must resolve relative to the files, not the current directory). The routes let the dashboard: list the tickets with their status, start the agent team on one ticket, read what the agents did, let a human approve (or reject) what the agents prepared, read the cash balance, and reset to the original data.
>
> Do NOT run the real agent team on any real ticket in this problem. The real run happens in a later problem and must start from the untouched working database. Test the run route with a stub in place of the agent runner, as described under Verify.
>
> Routes (prefix /api, JSON in and out):
> 1. GET /api/tickets: the three tickets with id, type, requester, subject, status (open, resolved or declined), plus the resolution note if there is one, and the number of pending approvals tied to that ticket if you can tell.
> 2. POST /api/tickets/{ticket_id}/run: starts the agent team (Boss with the full team) on that ticket. Because a run takes a while, return immediately with a run_id (HTTP 202) and run the team in the background. Provide GET /api/runs/{run_id} for status (queued, running, finished, stopped with the reason, error) and the Boss's final typed decision when finished. Rules: unknown ticket id gives 404; a ticket that isn't open gives 409; only one run at a time (a second request while one is running gives 409 with a clear message); the existing per-ticket limits from the agent config still apply.
> 3. GET /api/events: recent agent events from output/audit_trail.json, for the board to refresh: for each event the agent, step type, tool or delegate name, a short summary of what the agent said or what the tool returned, delegation depth, ticket id, run_id and time. Support ?after=<cursor> so the dashboard only fetches new events (return a next cursor), ?limit= (default 100, max 500) and ?run_id= to filter. Read-only. Never expose secrets; the audit writer already redacts them, and don't add raw prompt text.
> 4. POST /api/approvals/{proposal_id}/approve with body {"approved_by": "<name>"}: the human approval route. This is the ONLY route that moves money. It checks the proposal exists and is pending, records the human approval using the human-approval function from Problem 5 (the one that is not an MCP tool and not reachable by agents), and then:
>    - for a payment proposal, executes it by calling the MCP pay_approved tool through the MCP client (not by writing to the database directly), and returns the result with cash before and after;
>    - for a purchase-order proposal, marks it approved and returns it (no money moves, and inventory isn't changed);
>    - if the payment is refused (for example insufficient cash), return the refusal clearly, and put the proposal back to pending with the failure reason recorded, so that no half-approved payment lingers that an agent could execute later;
>    - already executed, already rejected, unknown id and empty or oversized approved_by (1 to 60 characters, trimmed) are all refused with clear errors; approving twice never pays twice.
>    Also add POST /api/approvals/{proposal_id}/reject (body with the person's name and an optional short reason) so a human can decline a proposal. Rejected proposals can never be paid.
> 5. GET /api/cash: the current checking balance and its as-of date, read through the MCP get_cash_balance tool.
> 6. POST /api/reset with body {"confirm": true}: restores data/campus_customs_new.db from data/campus_customs.db, and clears the three stores (approvals, drafts board, ticket resolutions) so a fresh run starts clean. It must NOT wipe or edit output/audit_trail.json (append a note entry saying a reset happened instead). Refuse while a run is in progress (409). After copying, verify the new file's SHA-256 equals the original's and return both checksums and the table row counts. Implement the reset as one shared function in scripts/reset_db.py that both this route and the command line use.
> Small read-only extras the dashboard clearly needs (list them in the harness as extras): GET /api/approvals?status=pending (the proposals waiting for a human, with kind, amount, vendor or invoice or lease, the reason and the agent that proposed it), GET /api/drafts (the customer drafts saved on the board), GET /api/health.
>
> Safety and quality rules:
> - Never let a route change shop data except the three that must: run (through the agents), approve (pay_approved) and reset. Reads are read-only.
> - Request bodies are Pydantic models with extra fields forbidden; validation errors must not echo the input back; ids are validated; generic messages for unexpected errors (log details server-side without secrets).
> - CORS: allow only the dashboard's origins, default http://localhost:5173 and http://127.0.0.1:5173, configurable by an environment variable. No wildcard.
> - All shop reads and writes go through the MCP server like before. Don't add a second layer that talks to SQLite directly, except the reset file copy.
> - Use the existing database path and store-path overrides so tests can point the whole backend at scratch copies.
> - Don't write to or log API keys. Don't change the model rules: gpt-6-luna only, and scripts/check_models.py must still pass.
>
> Docs:
> - Append to output/harness.md (don't delete or rewrite anything already there) a section "Backend routes" listing every route in one line each: method, URL, and what it does, with the extras marked as extras. Add one line on how to start the server and note that the approve route is the only route that moves money.
>
> Verify (with raw output):
> 1. Start the server exactly as `cd backend && uvicorn main:app --reload --port 8000` against the real working database, and call the read routes with curl: GET /api/health, /api/tickets (three tickets, all open), /api/cash (3400), /api/events (limit 5), /api/approvals?status=pending and /api/drafts (both empty). These must not change any file; show both database checksums afterwards, still 23686a90d698f7fa6f901a3f0a9774db9cbb31e13151c9e5717275f3321f360a, and show that the real stores still don't exist.
> 2. Stop that server. Start a second instance on another port, pointed entirely at scratch copies (database, stores, and an audit file copy), and test:
>    - approve flow: create a rent proposal and an invoice proposal and a purchase-order proposal using the MCP propose tools on the scratch copy; approve the invoice one through the route (cash falls, invoice paid, payments row has approved_by); approve it again (refused, no second payment); approve the rent one with an amount that makes cash short (use a scratch tweak) and show the refusal and that it returns to pending; approve the purchase order (no cash change); reject a proposal and show it can't then be approved or paid; bad names, empty names and unknown ids refused.
>    - run route with a stubbed runner: 202 with a run_id, status moves queued/running/finished, a second concurrent run gets 409, an unknown ticket gets 404, a resolved ticket gets 409. Also show that the route's real (unstubbed) runner function is the Problem 5 Boss entry point, by name, without calling the model.
>    - events route: new entries appear with the right cursor, ?after returns only newer ones, ?run_id filters, and the limit is capped.
>    - reset route: make a few changes in the scratch copy first, then reset; show the checksum equals the original, the stores are cleared, the audit file kept all its previous entries (count grew by the one note entry), and that reset is refused while a stubbed run is in progress and when confirm is missing or false.
>    - validation: extra fields rejected, invalid body gives a 422 that doesn't echo the input, CORS allows http://localhost:5173 and doesn't allow another origin.
> 3. Show that scripts/check_models.py still passes, and both real database checksums are still the original, and the real stores still don't exist, and output/audit_trail.json has only gained entries that came from tests labelled problem-7-route-test (or none).
> 4. Show the final backend/main.py, the new section of harness.md, and the list of routes FastAPI reports (from /openapi.json).

**Follow-up:** _none needed_

---

## Problem 7 — follow-up (harness fixes)

**Prompt 1:**

> Follow-up on Problem 7 (first append this prompt to AI_prompts.md verbatim). Two small harness.md fixes. Don't rewrite anything else.
>
> 1. In the "MCP tools" section, add the two backend-only tools (list_tickets, list_drafts) with the table or store each reads and a note that agents can't see them, so the harness lists all 19 tools and matches mcp_server/README.md.
> 2. In the "Safety" section, add a short, honest note that the approver's name is self-declared and the API has no login or authentication, which is acceptable for a local homework app but a real business would need real authenticated approvers. Also note the in-memory run history (lost on restart).
>
> Show the diff of harness.md (only those additions) and confirm the tool count in harness.md and the README are both 19.

**Follow-up:** _none needed_

---

## Problem 8 — Agent dashboard

**Prompt 1:**

> Problem 8: Agent dashboard
>
> First, append this prompt to AI_prompts.md verbatim, as usual.
>
> What I need: the desk where a person can watch the agent team work: a React + Vite + TypeScript app in frontend/ that talks to the backend I built in Problem 7 at http://localhost:8000. A person should be able to see all three tickets, choose one and start the team on it, watch each agent work in real time, see the ticket marked resolved when it finishes, read a short summary of what each agent did, approve or reject a payment or purchase when the team asks, and watch the checking balance drop after an approved payment. It should look like a real back office desk that people would enjoy sitting at, with real design thought, not a generic admin template.
>
> Do NOT run the real agent team and do NOT touch the real database, stores or audit trail in this problem. The real full run happens later from the untouched working copy. Build and test the UI against a scratch backend, as described under Verify.
>
> Start and wiring:
> - `npm run dev` from frontend/ starts the app on port 5173 (strictPort, so it always matches the backend's CORS list) and opens the browser.
> - The API base URL is http://localhost:8000 by default, set through one VITE_API_BASE env variable with a .env.example (placeholders only). No Vite proxy, since the backend already allows http://localhost:5173 and http://127.0.0.1:5173. Confirm that CORS works from the browser, and if anything about the backend's CORS needs adjusting, say so and make the smallest change.
> - Read backend/main.py first and build a typed API client (src/api.ts) that matches the real response shapes exactly. Strict TypeScript, no `any`. Use the existing routes: GET /api/tickets, POST /api/tickets/{id}/run, GET /api/runs/{run_id}, GET /api/events (with the `after` cursor and `run_id`), GET /api/approvals, POST /api/approvals/{id}/approve and /reject, GET /api/cash, GET /api/drafts, POST /api/reset, GET /api/health.
> - Stack notes: look at homework-4/frontend for the toolchain and config patterns (read only), but this is a different app, so don't copy its UI. Self-host any fonts with @fontsource and make no runtime requests to any external domain (no CDN, no Google Fonts). No API keys exist or are needed in the front end.
>
> What the board must do:
> 1. List all three tickets (id, type, requester, subject) with status from the API, including "open", "resolved" and "declined", and how many approvals are pending for each. A ticket that has pending approvals stays open: show it clearly as "open, waiting for a human" rather than implying it's done.
> 2. Let the person pick a ticket and start the team on it (POST run). Disable starting when a run is already in progress or the ticket isn't open, and show the backend's own message when it refuses (409 and so on).
> 3. While a run is in progress, show the five agents (Boss, Inventory, Accounting, Facilities, Customer Service) and what each is doing: idle, thinking, calling a tool (which one), asking another agent (which one), done, or stopped. Derive this ONLY from the events and run status the API returns (poll /api/events with the cursor, about every second during a run and slowly otherwise, pause when the tab is hidden). Show what each agent said and which tools it used. Show delegations between agents visibly, so the full-connectivity team reads as a team: who asked whom, in order.
> 4. When the run finishes, refresh the tickets so the ticket shows resolved (or still open, waiting for approval) from the API's status, and show the Boss's final decision (final_decision text, the actions, and whether human approval is needed). If the run stops at a limit or errors, show the reason plainly.
> 5. Show a short per-agent summary for that ticket: for each agent that took part, what it did (counts of tool calls and delegations, the tools it used, its final summary). Build it from the real events and the typed report data only. The front end must never invent text about what an agent did.
> 6. Approvals: list pending approvals (what it is for, amount, vendor or invoice or lease, the reason, which agent proposed it). Approve and Reject buttons open a confirmation that shows the exact amount and target, asks for the approver's name (self-declared, remembered in the browser as a convenience only), and says in plain words what will happen ("this will pay $X from checking" or "this approves a purchase order; no money moves"). Show the result: cash before and after on success, or the refusal reason when the backend refuses (such as insufficient cash), and that the proposal is back to pending.
> 7. Cash: show the checking balance and its as-of date, always fresh after approvals, after a reset, and after a run. When it changes, show the change (the drop and amount) in a clear, animated way that respects prefers-reduced-motion.
> 8. Customer drafts: a panel showing the drafts saved on the board (GET /api/drafts), clearly marked "draft, never sent".
> 9. A reset control (POST /api/reset with confirm) behind a clear danger-style confirmation, disabled during a run, that refreshes everything after.
>
> Resilience and safety in the UI:
> - If the backend isn't reachable, show a clear banner ("Can't reach the desk server at http://localhost:8000. Start it with `uvicorn main:app --reload --port 8000` from the backend folder") instead of a broken page. Handle slow responses and errors without raw stack traces.
> - Render all agent and ticket text as plain text (React escaping, no dangerouslySetInnerHTML, no markdown-to-HTML of agent output).
> - Money only moves from the Approve button's explicit confirmation. No automatic approvals, and no keyboard shortcut that approves.
>
> Design brief (make real choices and commit to them):
> - The feel: a physical back-office desk for a campus print shop, with a point of view. Think of paper tickets and clipboards, a till or ledger for cash, a stamp for "resolved", slips that need a signature. Pick one coherent concept and carry it through layout, type, color, motion and copy. No generic dashboard template look, no purple gradients, no glassmorphism, no stock icon-grid look.
> - The five agents must read as five distinct colleagues, not five identical boxes: give each its own role label, typographic voice or mark, and a distinct shape or icon, and don't rely on color alone. Keep their states legible at a glance.
> - Resolved tickets should feel resolved (a satisfying, quick visual change), and still-open-but-waiting tickets should feel different from both. Cash should feel like money on a ledger or till, with the drop being a moment.
> - Use a restrained palette that may draw on the Campus Customs brand (navy, cream, gold) but make the desk its own thing. Original abstract graphics only: no mascots, no real logos, no copyrighted characters.
> - Accessibility: WCAG AA contrast, visible focus, full keyboard operation, sensible ARIA (a polite live region for new agent events that doesn't flood screen readers), prefers-reduced-motion respected, usable at phone width (stacked layout) and comfortable on desktop (a multi-column desk).
> - Keep it fast: no heavy libraries needed; small bundle.
>
> Docs:
> - Write output/design.md: what you chose for the dashboard look and why: the concept, the layout, how the five agents read differently, how resolved tickets and cash show up, the creative choices that make it enjoyable to use, accessibility decisions, and the states you designed (idle, running, waiting for approval, resolved, error, backend down). Ground it in what you actually built (refer to the screenshots you took), and be honest about limits.
> - Add a short frontend/README.md with how to install and start it, and the one environment variable.
> - Don't rewrite anything already in output/harness.md. If you add anything there, only append a short "Dashboard" line.
>
> Verify (with raw output, and screenshots shown to me):
> 1. `npm run build` (with strict TypeScript) and the lint command pass with no errors; show the raw output. Add a few unit tests for the pure logic (the function that derives each agent's state and summary from events, and the money or status formatting), and show them passing.
> 2. Use scratch data only: point a second backend instance at scratch copies of the database, stores and audit file (the environment overrides from Problem 7), with the stub runner. For the screenshots, make the stub runner able to play back a clearly labelled scripted demo (a few agents delegating, tool calls, a proposed payment made through the real MCP propose_payment tool on the scratch copy, and a resolve at the end), implemented so that it refuses to run unless every path points at scratch. Mark all demo audit entries with run_label "dashboard-demo". Tell me exactly how you implemented it and where.
> 3. Drive the real UI in a browser against that scratch backend and take screenshots at desktop and phone width of: the initial board; a run in progress (agents active, delegations visible); the finished run with the ticket resolved and the agent summaries; the approval confirmation; after approval with the cash drop shown; a refusal (insufficient cash on the scratch copy); the backend-down banner (backend stopped); and the reset confirmation. Also check: keyboard-only operation of run, approve and reset, and the reduced-motion setting, and show that the page makes no requests to any domain other than localhost:8000 and its own dev server.
> 4. Confirm no real file was touched: both real database checksums still 23686a90d698f7fa6f901a3f0a9774db9cbb31e13151c9e5717275f3321f360a; the three real stores still don't exist; output/audit_trail.json is still 144 entries (or whatever it was before this problem, show the count before and after); scripts/check_models.py still passes.
> 5. Show the final file tree of frontend/ (excluding node_modules), the contents of output/design.md, and the list of anything you changed outside frontend/ and output/design.md.

**Follow-up:** _none needed_

---

## Problem 9 — Resolve the tickets

**Prompt 1:**

> Problem 9: Resolve the tickets
>
> First, append this prompt to AI_prompts.md verbatim, as usual.
>
> What I need: the real run. Start the shop from a clean slate, run the agent team on all three open tickets (101, 102, 103) on the board until each is resolved, and then record exactly what happened: on the planning page, in a results file, in a page of screenshots, in the audit trail and in the harness. All of it must come from what actually happened (database, stores, audit trail), never from what you or I expected.
>
> Hard rules (these matter more than finishing):
> - NEVER approve or reject anything yourself. Do not call the approve or reject routes, scripts/approve.py, or the pay_approved tool, and don't edit the approvals store or the database by hand, not even "on my behalf" or with a made-up name. I click Approve in the dashboard myself, typing my own name. If proposals are waiting, stop and tell me (see "Stop points"), then wait for me.
> - Don't call resolve_ticket by hand, don't edit any database or store file, and don't write any agent output yourself. Everything must come from the team's own runs through the app.
> - Keep the limits in the config as they are. Don't raise any limit, and don't change prompts, code or tools while a run is in progress.
> - Model rule unchanged: gpt-6-luna only. scripts/check_models.py must still pass at the end.
> - If a bug or a bad agent behaviour blocks progress, stop and report what you found with the raw evidence and the smallest fix you propose. Don't silently patch it. If we do fix something, we reset and restart the whole run from the beginning, so the final database, cash and audit trail reflect one clean run. Entries from the abandoned attempt stay in the audit trail (never delete them).
> - Cap: at most 4 runs per ticket (a ticket may need a second run after a human approval, since the Boss must not resolve a ticket while an approval it depends on is pending). If a ticket is still open after 4 runs, stop and report why.
>
> Step 1: Prepare
> 1. Make sure nothing else is using ports 8000 and 5173. If something is, tell me what, and don't kill any process you didn't start.
> 2. Start the backend from backend/ with CAMPUS_CUSTOMS_RUN_LABEL=problem-9-full-run exactly as `uvicorn main:app --reload --port 8000` (the real runner, never the stub or demo mode; show /api/health proving runner is main.default_runner), and start the dashboard with `npm run dev` in frontend/ on port 5173 so that I can open it. Keep both running for the whole problem, and tell me the URL.
>
> Step 2: Reset to a clean start
> 1. Reset with POST /api/reset ({"confirm": true}) through the shared reset function. Show the response: checksum equal to the original (23686a90d698f7fa6f901a3f0a9774db9cbb31e13151c9e5717275f3321f360a), the stores cleared, the audit trail kept (entry count before and after).
> 2. Read the starting checking balance from the database (read-only query) and via GET /api/cash. Show both and note it as the "starting balance".
> 3. Show the starting state of the tables the run can change: tickets (status), invoices, leases (next_due), payments (count), cash_accounts.
>
> Step 3: Run the tickets
> - Run 101, then 102, then 103, using POST /api/tickets/{id}/run (the same route the dashboard button calls), one at a time (the backend allows only one run). Poll GET /api/runs/{run_id} until it finishes, and show each run's final status, the Boss's decision and the usage numbers (requests, tool calls, tokens if available).
> - After each run, show the ticket's status from GET /api/tickets, the pending approvals from GET /api/approvals?status=pending, and the drafts.
>
> Stop points (human approval):
> - Whenever any proposals are pending after a run, STOP. List each one for me: proposal id, kind, amount, target (invoice, lease, vendor and SKU), the reason, the proposing agent and the ticket. Then wait for me to reply that I've approved or rejected them in the dashboard. Don't proceed, poll for my action, or nudge me to approve. After I reply, verify through the API and the database what actually happened (executed payments, cash before and after) and continue.
> - After my approval, re-run the ticket if it is still open (up to the cap). Keep going until every ticket is resolved, or declined. If the Boss legitimately declines a ticket, that's a valid final status. Report it clearly and ask me before treating the problem as complete.
>
> Step 4: Record the results (all derived from the database, stores and audit trail)
> 1. output/desk_tickets.html (from Problem 6): fill each ticket tab's Actual section from this run: who the Boss called first (and the stated reason only where the audit trail or the Boss's decision actually records one; otherwise write "not recorded"), the delegations that really happened (every agent-to-agent hand-off, in order), the MCP tools that were actually used (distinct names, from the audit trail), across all runs of that ticket. Also add, plainly and mechanically, under each Actual section: tools that were in my Expected list but not used, and tools used that were not in my Expected list, and delegations expected but not made / made but not expected (a computed set difference, with no interpretation). Don't change my Expected sections in any way: before editing, extract the Expected text of all three tabs to a scratch file, and after editing, prove with a diff that they're byte-identical. Keep the section ids and the page offline and self-contained. Leave the Reflection tab as it is.
> 2. The Cash tab of the same page, itemized, with every number from the database:
>    - Starting checking balance (after the reset).
>    - For each ticket (101, 102, 103): how cash changed because of it and why: each payment (payments row id, kind invoice or rent, reference, dollar amount, who approved, when), or "no cash change" with the reason (for example a purchase order was approved but no money moves, or nothing was approved). Attribute each payment to the ticket whose run proposed it, using the audit trail and proposals, and say so.
>    - Ending checking balance, and show that it equals cash_accounts in the working database now: starting balance minus the sum of the payments rows equals the ending balance equals the database value. Show the arithmetic on the page and in your report, and state the timestamp of the database read.
> 3. output/resolved_tickets.json: valid JSON with, for each ticket: id, type, requester, subject, final status, a short outcome in plain words, what each agent contributed (agent, what it did, tools used, from the audit trail and reports), the human approvals (proposal id, kind, amount, approved or rejected, approver name, time), the run ids, any customer draft ids, and the resolution note. Also a top-level section for the database state after the run (cash balance, payments rows, invoice statuses, lease next_due, ticket statuses) and the starting balance. Validate it with a JSON parser, and cross-check every number against the database.
> 4. output/resolved_board.html: a self-contained page I can double-click (images embedded so it's a single file, compressed so the whole file stays under about 4 MB) showing a screenshot of my React board for each resolved ticket (101, 102, 103). Take the screenshots with a headless browser from the REAL dashboard at the point each ticket is resolved with the finished run visible (the board keeps run memos in server memory, so capture while the backend is still running and before any restart): the ticket stamped resolved, the agents, the Boss's memo and summaries, and the till. Don't use the scripted demo screenshots. Label each screenshot with its ticket and the time it was taken. If a ticket needed several runs, show the final run's board and say how many runs it took.
> 5. Make sure the appended entries in output/audit_trail.json from these real runs are labelled problem-9-full-run, show the entry count before and after, show that earlier entries were not modified, and that the only model named is gpt-6-luna.
> 6. Finish output/harness.md so it covers, completely and consistently: the database tables, all 19 MCP tools (agents' tools and the two backend-only ones, with the table or store each uses), the five agents (role, tools, who each can delegate to), all API routes with one line each (including extras), the dashboard (a short summary and a pointer to design.md), the safety rules (what is enforced in code and what is only in prompts; the self-declared approver name and no login; in-memory run history; the one-time audit redaction exception), plus a new "Full run results" section summarizing what really happened per ticket and the cash itemization, with honest notes on anything that surprised us, any limit that was hit and any run that needed repeating. Fix anything in the harness that has become stale or inconsistent with the final system (for example tool counts). Don't delete my earlier content unless it is wrong, and tell me about any such edit.
>
> Verify and report (raw output, not summaries):
> - The reset response and the starting state; each run's status, decision and usage; every stop point's list of proposals as you showed me; and, after my approvals, the payments rows and cash before and after.
> - The final database tables (tickets, invoices, leases, payments, cash_accounts, and any other table that changed) with the arithmetic for the ending balance.
> - The proof that my Expected text is unchanged (diff output).
> - Validation of resolved_tickets.json and the cross-check against the database.
> - Screenshots of the three real board states, and a screenshot of each tab of desk_tickets.html (Ticket 101, 102, 103, Cash).
> - The original database checksum is still 23686a90d698f7fa6f901a3f0a9774db9cbb31e13151c9e5717275f3321f360a; check_models.py passes; both servers' final status; the audit trail counts.
> - A short list of anything that did not go to plan.

**Follow-up 1** (after the first stop point, when PAY-0001 was waiting):

> I've approved the rent payment

**Follow-up 2** (my decisions on ticket 103's decline and the screenshot view):

> Decisions on your two questions (first append this reply to AI_prompts.md verbatim):
>
> 1. Ticket 103: I accept "declined" as its final status. Don't rerun it. Record DRAFT-0002's wording honestly: it says "the approved bulk price of $52.20" although nobody approved that price (Accounting only recommended it), and it offers 8 hoodies on a ticket the Boss declined. It was never sent. Don't edit or delete the draft. Put this in the "Full run results" section of harness.md as a guardrail finding (Customer Service's prompt says never to offer an undecided discount, and the draft did anyway), and in the 103 entry of resolved_tickets.json (as a note on the customer draft). Don't change any prompt now.
>
> 2. Screenshots: yes, add the read-only ?run=<run_id> view in the frontend only. Rules: don't touch any backend .py file (the --reload watcher would restart the server and wipe the run memos in memory) and don't restart or stop the backend or the demo servers' state; don't re-run anything. Add a unit test for the URL handling, keep build, lint and tests passing, document the ?run= view in frontend/README.md and design.md (one short paragraph, saying it opens a finished run read-only from server memory). Then take the three screenshots from the real dashboard with that view, label each with its capture time and the note that the till shows the balance at capture time (not the balance when that ticket resolved), say how many runs each ticket took, and embed them in output/resolved_board.html as specified.
>
> Then continue with everything still left in Step 4 and the verification from my Problem 9 prompt: the Actual sections and Cash tab in desk_tickets.html (with my Expected text proven byte-identical by diff), resolved_tickets.json cross-checked against the database, the audit-trail checks, the finished harness.md, and the final report. For the Cash tab, attribute the rent payment to the ticket whose run proposed it, state that invoice 501 remains open and unpaid (if that is what the database shows) and say why that matters for tickets 101 and 103, and show the arithmetic: starting balance minus the sum of the payments rows equals the ending balance equals the database value. Report any surprises plainly.

_What was lacking after the first prompt:_ it didn't anticipate that the Boss would close tickets on its
own (102 while its payment was still pending, 103 as declined), or that board screenshots need the
dashboard to be able to open a run it didn't start itself.

---

## Problem 10 — Reflection

**Prompt 1:**

> Problem 10: Reflection
>
> First, append this prompt to AI_prompts.md verbatim, as usual (including the reflection text below).
>
> What I need: fill the Reflection tab of output/desk_tickets.html with my reflection text, exactly as I give it below. Don't touch anything else on the page.
>
> Rules:
> - Use my text word for word. Don't edit, polish, shorten, reorder or add to it. Render each block separated by a blank line as a paragraph, and each line starting with "- " as a list item, and the lines marked HEADING as headings. Nothing else gets interpreted. Escape everything so it displays exactly as typed.
> - The Expected, Actual and Cash content of all four other tabs must stay byte-identical. Before editing, extract those sections to a scratch file; after editing, prove with a diff that they are unchanged.
> - Give the reflection sections stable ids (reflection-evaluation, reflection-plan-vs-actual, reflection-one-agent, reflection-solvable, reflection-unsolvable). Keep the page offline and self-contained (no external requests), keyboard accessible, readable at phone width, printable, and still readable with JavaScript disabled, like the other tabs.
> - Don't run any agent or model, don't touch the database, stores, audit trail, backend or frontend, and don't restart any server. Only output/desk_tickets.html and AI_prompts.md may change.
> - Fact check, without changing my words: after saving, check every factual claim in my text against the database, output/resolved_tickets.json, the audit trail and the run records, and show me a table (claim, evidence, matches yes/no). If any claim doesn't match, DO NOT fix it: tell me exactly which claim and what the evidence says.
>
> My reflection text:
>
> HEADING: 1. How I'd evaluate the agents on each ticket, and why
>
> I judged each ticket on three things: did the facts match the database, did the agents follow the shop rules, and was the outcome actually good for the shop. I picked these because this team touches real-looking money and customers, so a confident wrong number or a broken rule matters more to me than how fast it ran.
>
> Ticket 101 (Bulldog tee, size S):
> - Facts: good. The S tee really is at 0 in stock and the numbers matched the database.
> - Rules: clean. No money moved, no discount was offered, and the reply is a draft (DRAFT-0001) that was never sent.
> - Outcome: okay but incomplete. It resolved, but the real blocker, overdue invoice 501 holding the vendor, only showed up as a remark in the Boss's memo. Nobody proposed paying it, so the S tee still can't be restocked.
>
> Ticket 102 (rent):
> - Facts: good. Rent of $2,400 due 2026-09-02 against $3,400 in checking all matched the database.
> - Rules: mixed, and this is the weak spot. The money side was safe: the payment was only proposed (PAY-0001) and moved after I approved it in the dashboard, and cash never went negative. But the Boss resolved the ticket while the payment was still pending, which its own prompt forbids. Nothing in code stops that, so it's a prompt rule that didn't hold.
> - Outcome: good in the end. Rent was paid, checking went from $3,400 to $1,000 (see the Cash tab), and the lease's next due date moved to 2026-10-02.
>
> Ticket 103 (20 hoodies, discount request):
> - Facts: good. 8 of 20 size M hoodies in stock (short by 12), list price $58, cost $22.
> - Rules: the biggest miss. The price floor held, because Accounting's recommended $52.20 (10% off $58) is well above the $22 cost. But Customer Service wrote DRAFT-0002 calling $52.20 "the approved bulk price" when nobody approved it, and it offers 8 hoodies on a ticket the Boss declined. It was never sent, but a customer would have read a promise we hadn't made.
> - Outcome: defensible, not great. Declining makes sense with 8 in stock and the restock blocked by invoice 501, but checking holds $1,000 and the invoice is $840, so a better outcome might have been to keep the ticket open and propose paying 501 first.
>
> HEADING: 2. How Actual compared to my Expected plans
>
> The biggest difference is that I expected specialists to pass work to each other, but the Boss centralized everything. Across all three runs no specialist ever handed work to another specialist. The Boss did all the routing, so the agent-to-agent links the team has (20 possible) went unused.
>
> - Ticket 101: the closest match. I expected Inventory first and then Customer Service, with no Accounting, and that is what the Boss did (Boss to Inventory, Boss to Customer Service). What I didn't plan for was the memo mentioning an invoice approval that no agent ever proposed. The exact tools used are in the Actual section of the Ticket 101 tab.
> - Ticket 102: I expected the Boss to call Facilities and then Facilities to ask Accounting to propose the payment. Instead the Boss asked Facilities and Accounting itself, directly. The end result was what I wanted (PAY-0001 for $2,400, itemized on the Cash tab), but the route was flatter, and I didn't predict the Boss would close the ticket before my approval.
> - Ticket 103: I expected Inventory first (can we even fill 20?) with Inventory then asking Accounting. The Boss called Accounting first, then Inventory, then Customer Service. The order was different but the same three specialists were involved, and the decision to decline leaned on the two facts I thought mattered: stock and the vendor hold. I also didn't predict the bad DRAFT-0002.
>
> What this tells me: my plans imagined a team passing the baton, while the Boss behaves like a manager who hands out every task personally. That is simpler to audit, since every hand-off starts at the Boss, but it means the specialist-to-specialist links I built are decoration so far.
>
> HEADING: 3. What would have been simpler as one agent with tools
>
> Ticket 102 (rent). The job was basically three steps: read the lease (get_lease), check the checking balance (get_cash_balance) and propose the payment (propose_payment). The team spent 12 requests and 13 tool calls, about 72 seconds and about 40k input tokens, with the Boss routing to Facilities and Accounting, just to do those three things. One agent holding those three tools could have done it with fewer hand-offs and less to go wrong.
>
> What I would not collapse is the approval step. The human approval and the refusal on insufficient cash are enforced in the tools and the backend, so they stay safe whether there is one agent or five. The rule that did fail (resolving before approval) is only a prompt rule, so a single agent wouldn't have been automatically better there either. It needs a check in code.
>
> For 101 and 103 it felt less clear-cut. They needed judgment calls (what to tell a customer, how low a price can go), and splitting those across roles at least gave me a separate record per agent in the audit trail.
>
> HEADING: 4. Three problems the team could solve with the tools I built
>
> - Next month's rent. Lease 1 now comes due 2026-10-02 ($2,400 monthly). Facilities and Accounting can read it with get_lease, check cash with get_cash_balance, see whether it was already paid with list_payments, and propose it with propose_payment for a human to approve. One honest catch from the Cash tab: checking is only $1,000 after this run, so pay_approved would refuse a $2,400 payment (no negative balances). The team could spot and prepare the bill, not fund it.
> - A zero-stock mug. CC-MUG-CREST is at 0 in stock. Inventory would confirm with check_stock, find Elm City Gifts (mugs and small goods, 3-day lead) with list_vendors, and confirm the vendor has no open unpaid invoice with get_vendor_open_invoices. Accounting would then use propose_purchase_order, which comes back pending for a human to approve. I tested this pattern on a scratch copy of the database in Problem 5 (a 24-mug order arriving three days out), though no real ticket asked for it.
> - Another overdue vendor bill. Invoice 501 is exactly this: Bulldog Print Co, $840, overdue. The tools cover it end to end: get_invoice, get_vendor_open_invoices and get_cash_balance, then propose_payment, human approval and pay_approved. The funny part is that it's the one problem in this run the team could have solved but didn't. Checking had $1,000 (see the Cash tab), more than the $840, yet no run proposed it, and that is why the tee in 101 and the hoodie restock in 103 are still stuck.
>
> HEADING: 5. Three problems the team could not solve, and what I'd need
>
> - Receiving a restock. Even a fully approved purchase order doesn't change inventory, and nothing records a delivery, so shortages like the 8 vs 20 hoodies in 103 or the S tee at 0 in 101 would never close in the data. I'd need a purchase order status that moves from approved to ordered to received, a receive_stock tool that adds the delivered quantity to inventory only against an approved purchase order (and writes to the audit trail), a record_vendor_invoice tool so the bill that comes with the delivery lands in the invoices table, and a Receiving agent (or a new job for Inventory) that checks what arrived against what was ordered.
> - Vendor quotes and price comparison. The data only knows three vendors by specialty and lead time (Bulldog Print Co, Elm City Gifts and a local courier), and the only cost figures are the shop's own unit_cost in the pricing table. For the 12-hoodie shortfall in 103, the team can't compare vendors or know the real cost of a restock. I'd need a vendor catalog and quote table, tools like get_vendor_quote(vendor, sku, qty) and compare_quotes, and a Sourcing agent that Accounting and Inventory can call, with the margin check against the discount floor.
> - Returns, refunds and order history. There is no customers or orders table: the requester is just free text (like the Yale AI Club on ticket 103), and the cash model only goes out, with revenue not modelled, so a customer who says they were charged for the wrong size can't be verified or refunded. I'd need orders and customers tables, a get_order_history tool, a propose_refund tool that goes through the same human approval as payments (and puts money back into cash), and a Returns agent that checks the order, checks stock of the replacement size and drafts the reply.
>
> Checks (with raw output):
> - Screenshots of all five tabs of the page (Ticket 101, Ticket 102, Ticket 103, Cash, Reflection), including the Reflection tab at phone width and with JavaScript disabled, and proof that the page makes no network requests.
> - A diff proving my text appears in the Reflection tab character for character, and the diff proving the other tabs' Expected, Actual and Cash content is unchanged.
> - The fact-check table.
> - Confirmation that both database checksums are still the original (23686a90d698f7fa6f901a3f0a9774db9cbb31e13151c9e5717275f3321f360a) and that only output/desk_tickets.html and AI_prompts.md changed.

**Follow-up:** _none needed_

---

## Problem 10 — follow-up (Reflection wording fix)

**Prompt 1:**

> Small wording fix to the Reflection tab (first append this prompt to AI_prompts.md verbatim). Change exactly these two phrases and nothing else:
>
> 1. In section 1, under Ticket 101, replace this whole line:
> "- Outcome: okay but incomplete. It resolved, but the real blocker, overdue invoice 501 holding the vendor, only showed up as a remark in the Boss's memo. Nobody proposed paying it, so the S tee still can't be restocked."
> with:
> "- Outcome: okay but incomplete. It resolved, and the team did notice the real blocker: overdue invoice 501 is holding the vendor, and it appears in the Boss's findings, the resolution note and Inventory's report. But nobody turned that into a payment proposal, so the S tee still can't be restocked."
>
> 2. In section 3, replace "about 72 seconds" with "about 71 seconds".
>
> Show a diff of the Reflection tab text before and after proving only those two edits changed, prove the other four tabs' Expected, Actual and Cash content is still byte-identical, and show that only output/desk_tickets.html and AI_prompts.md changed.

**Follow-up:** _none needed_

---

## Privacy scan

**Prompt 1:**

> Privacy scan (read-only; first append this prompt to AI_prompts.md verbatim). Change nothing in the project.
>
> Goal: find everywhere my personal details appear, so I can keep them out of the public GitHub repo. I'll decide what to redact afterwards.
>
> 1. Work out the identifiers to look for, without printing any of them or writing them to any file: the approver name stored in the payments table's approved_by value and in the approvals store (and its separate first-name and last-name parts), the local part of my email address, and my computer's home-folder username (as it appears in absolute paths). Refer to them only as <APPROVER_FULL>, <APPROVER_FIRST>, <APPROVER_LAST>, <EMAIL_LOCAL> and <HOME_USER> in everything you show me.
> 2. Search the whole project, case-insensitively, excluding node_modules, .venv and __pycache__: all text files (including output/audit_trail.json, output/resolved_tickets.json, output/harness.md, output/design.md, output/desk_tickets.html, output/resolved_board.html, AI_prompts.md, README files, docs, scripts, tests, frontend/src and backend), and also data/ (the stores and the database). For each identifier, show a table: file, number of matches, and for each match a masked context line with the identifier replaced by its placeholder (never print the real value).
> 3. Mark each file as "published" or "local only" according to what .gitignore would exclude (data/ and .env should be local only).
> 4. Images: output/resolved_board.html embeds screenshots, and there are PNGs under output/ (including output/dashboard_screenshots/). Check whether any image shows the approver's name or any other personal detail (look at the actual screenshots, especially anything taken after the payment approval, the approval slips, signing dialogs and the till tape). Tell me which images show it and where in the image, without writing the name.
> 5. Also tell me: what git identity (name and email) a commit from this folder would currently use, whether the folder is already a git repo, and what any absolute paths found look like (masked).
>
> Finish with a short summary: which published files contain which identifiers, and anything else that looks personal.

**Follow-up:** _none needed_

---

## Problem 11 — Submit to GitHub

**Prompt 1:**

> Problem 11: Submit to GitHub
>
> First, append this prompt to AI_prompts.md verbatim, as usual.
>
> What I need: package the project and publish it as a public GitHub repo that graders can clone and run, and keep my personal details out of it. Build the publishable copy as a separate folder, scan it, and show me the results BEFORE anything is pushed. Wait for my "go". After the push, verify from the public URL.
>
> Rules:
> - Never modify my working project files for publishing. All publishing changes (redactions, trimmed screenshots, the README, extra files) apply only to the export copy. Build the export in a new sibling folder named hw5 (the repo layout at its root), using a whitelist copy, not a copy-everything-then-delete.
> - Never publish the real .env, my API key, or any secret. Publish .env.example with placeholders only.
> - Never write my real name, my email, my git identity or my computer's username into any file, log, prompt log, commit or message. Identify them only programmatically, as in the earlier privacy scan, and show them only as placeholders (<APPROVER_FULL>, <APPROVER_FIRST>, <APPROVER_LAST>, <EMAIL_LOCAL>, <HOME_USER>).
> - Don't run any agent or real model call in this problem (no token spend). Don't touch my working data/ files or either running server.
>
> What the repo must contain (the expected layout, plus what the code needs to run):
> - Root: AI_prompts.md, requirements.txt, .env.example, .gitignore, .mcp.json, mcp.json, README.md. The task layout lists "mcp.json" while Claude Code reads ".mcp.json", so ship both as byte-identical copies and mention this in the README (".mcp.json is the file Claude Code reads; mcp.json is an identical, visible copy").
> - data/: campus_customs.db (the ORIGINAL, byte-identical, checksum 23686a90d698f7fa6f901a3f0a9774db9cbb31e13151c9e5717275f3321f360a) and campus_customs_new.db (the working copy in its post-run state, with the approver redacted as described below). Don't publish the three stores (approvals, drafts board, ticket resolutions), lock files or backups. A fresh clone must work without them.
> - mcp_server/ (server.py, its helpers, README.md), backend/ (main.py, models.py, agents, audit and approvals code, demo_runner.py, prompts/ with the five prompt files), frontend/ (source, package.json, package-lock.json, config; no node_modules, dist or .env), output/ (harness.md, mcp_smoke.json, desk_tickets.html, design.md, resolved_tickets.json, resolved_board.html, audit_trail.json, github_url.txt), and any scripts/ and tests the code needs. Note that backend/main.py loads scripts/reset_db.py, so scripts/ must ship. Build the whitelist from what the code actually imports and loads, and let the fresh-clone test prove nothing is missing.
> - output/dashboard_screenshots/: keep it only if you can compress it to under about 3 MB in total with the images still legible (resize to a sensible width, optimize); otherwise keep a subset of the key states and fix the references to it in design.md in the export copy. Add a one-line README.txt in that folder saying they come from a scripted demo on scratch data.
> - .gitignore: must exclude .env, .venv/, node_modules/, dist/, __pycache__/, lock files, corrupt-file backups and the three stores. It must NOT exclude data/campus_customs.db or data/campus_customs_new.db. Prove it with git check-ignore on every important path.
> - output/github_url.txt: a single line with the final public URL.
>
> Privacy redaction (export copy only):
> - Replace the human approver's name (the value in the payments table's approved_by in my working database, and its first-name and last-name parts if they appear on their own) with the placeholder "[human approver]" in: output/harness.md, output/resolved_tickets.json, output/desk_tickets.html, and the exported copy of data/campus_customs_new.db (UPDATE payments.approved_by in the exported copy). Everything else stays identical. Confirm: resolved_tickets.json still parses; the exported database's cash_accounts balance, payments amount and all other values are unchanged; the Expected text in desk_tickets.html is still byte-identical to my working version; and a diff between my working files and the export copy shows ONLY those substitutions (show the diff with the name masked).
> - Add one short sentence to the README: the approver's name in the published outputs and working database was replaced by "[human approver]".
> - Scan the whole export tree for every identifier (the approver's full, first and last names, the email local part, the home username, and the git identity), including inside the SQLite files (check their raw bytes and table contents), the JSON and HTML, and any absolute paths such as /Users/.... Expect zero hits. Don't count a coincidence inside embedded base64 image data, but say if you found one. Also check that no image in the export shows the name.
> - Secrets scan: confirm the real API key value occurs 0 times in the export (and later in the git history), no token-shaped strings, no .env, nothing over 5 MB, and show the largest 10 files.
>
> README.md: a clear README, tested step by step on a fresh clone. It must explain: what the project is (one paragraph); the layout; prerequisites (Python version, Node version); setup (virtual environment, pip install -r requirements.txt, copy .env.example to .env and set PORTKEY_API_KEY, npm install in frontend/); that both databases are included and what each is (the original is read-only and never modified; the working copy is where runs write; the published working copy is the state after my run); how to copy the original database to the working copy when a clean run is needed (state the plain `cp` command and that scripts/reset_db.py --confirm and POST /api/reset do the same and also clear the stores); how to start the MCP server (explain that `python mcp_server/server.py` runs it standalone over stdio for MCP clients such as Claude Code through .mcp.json, and that the backend starts its own copy per request, so the MCP server doesn't need a separate terminal for the dashboard; make the interpreter path in .mcp.json consistent with the setup you describe); how to start the FastAPI backend (`cd backend && uvicorn main:app --reload --port 8000`); how to start the React board (`cd frontend && npm run dev`, open http://localhost:5173); how to reset the database BEFORE a full three-ticket run and then run tickets 101, 102 and 103 from the board, including the human approval step (a human clicks Approve; agents only propose); what the model rule is (gpt-6-luna only, via Portkey); what my own run produced (101 resolved, 102 resolved, 103 declined; checking $3,400 to $1,000), stated as the author's run, not a guarantee; and pointers to output/harness.md and output/design.md. Keep it concise and accurate.
>
> Git:
> - Use a repo-local git identity that is a noreply identity, the same pattern as the hw4 export repo (read its local config, don't change it). Never use the global git config. Show `git log --format='%an <%ae> | %cn <%ce>'` after committing and confirm it contains no real name or email.
> - Make a single initial commit.
> - Create the public repository named hw5 under the same GitHub account and by the same method as hw4 (check how hw4 was created and its remote owner). If hw5 already exists, stop and tell me.
>
> Verify, with raw output:
> A. BEFORE pushing, in the export folder: the tree (with sizes), the privacy and secrets scan results, the .gitignore check, the redaction diff (masked), the original database checksum, and README.md in full. Run scripts/check_models.py on the export. Then do a FRESH-CLONE TEST from a local clone of the export (git clone into a temp folder, not the folder itself): create a venv, pip install -r requirements.txt, follow the README exactly, and show that: the backend starts from backend/ with the README command, and /api/health, /api/tickets and /api/cash respond (use a dummy value for PORTKEY_API_KEY; don't make model calls); the MCP server lists 19 tools and answers one read call (such as check_stock) through the real MCP client; `npm ci` (or install) and `npm run build` pass in frontend/; POST /api/reset ({"confirm": true}) works in the clone and afterwards data/campus_customs_new.db equals the original checksum (23686a90...) and all three tickets are open with cash $3,400; the README steps worked as written (fix the README if not). Then STOP: summarize the results and wait for me to reply "go".
> B. After my "go": create the public repo, push, and verify as an anonymous visitor (no token) that https://github.com/<owner>/hw5 returns the repo and the raw files for .env and the three stores do NOT exist while README.md, .env.example and both databases do. Clone from the public URL into a new temp folder and re-run a quick version of the fresh-clone test (health, tickets, MCP tool count, frontend build). Re-scan the cloned working tree and `git log` for all identifiers and the API key. Confirm output/github_url.txt contains exactly the public URL. Show the final file list from the GitHub API.

**Follow-up:** _none needed_
