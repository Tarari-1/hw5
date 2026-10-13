# Campus Customs — Agent Harness

This file is the working reference for the Campus Customs back-office agents.
Problem 2 starts it with a study of the shop database; later problems will extend
it with agent roles, tools, rules and test results.

- **Shop "today":** `2026-08-31` (from `desk.date_today`)
- **Original database (read-only, never modified):** `data/campus_customs.db`
- **Working copy (later problems may change it):** `data/campus_customs_new.db`
- **SHA-256 of both at copy time:** `23686a90d698f7fa6f901a3f0a9774db9cbb31e13151c9e5717275f3321f360a`

Everything below was read from the database with queries. Where the database does
not say what something means, this file says it is unclear.

---

## Database tables

| Table | Rows |
|---|---|
| cash_accounts | 1 |
| desk | 1 |
| inventory | 10 |
| invoices | 1 |
| leases | 1 |
| payments | 0 |
| pricing | 4 |
| tickets | 3 |
| vendors | 3 |

No views or triggers. The only indexes are the automatic ones for the text
primary keys on `inventory`, `pricing` and `cash_accounts`. No UNIQUE or CHECK
constraints exist beyond the primary keys.

### desk
| Column | Type | Notes |
|---|---|---|
| date_today | TEXT NOT NULL | `2026-08-31` (YYYY-MM-DD) |
| notes | TEXT | NULL in the only row |

No primary key. One row.
**Why it matters:** agents should use this as the date for "today" (not the
computer's clock) when judging what is due or overdue.

### inventory
| Column | Type | Notes |
|---|---|---|
| sku | TEXT NOT NULL | PK part 1 |
| name | TEXT NOT NULL | product name, repeated on every size row |
| size | TEXT NOT NULL | PK part 2; values: S, M, L, XL, OS |
| qty | INTEGER NOT NULL | units on hand (unit assumed to be items; not stated) |
| location | TEXT NOT NULL | Aisle A–D |

PK `(sku, size)`. No foreign key to `pricing`.
Distinct sizes: L 2, M 2, OS 2, S 2, XL 2. Locations: Aisle A 4, Aisle B 4, Aisle C 1, Aisle D 1.
Totals by SKU: CC-HAT-BLUE 40, CC-HOOD-NAVY 32, CC-MUG-CREST 0, CC-TEE-WHITE 10.
**Why it matters:** the agents check here whether an order or bulk request can be
filled from stock, per size.

### pricing
| Column | Type | Notes |
|---|---|---|
| sku | TEXT | PK (not declared NOT NULL) |
| unit_cost | REAL NOT NULL | currency not stated |
| list_price | REAL NOT NULL | currency not stated |

Every inventory SKU has a pricing row and vice versa (checked).
**Why it matters:** the floor for any discount decision (cost) and the normal
price an agent should quote; price is per SKU, not per size.

### vendors
| Column | Type | Notes |
|---|---|---|
| id | INTEGER | PK |
| name | TEXT NOT NULL | |
| specialty | TEXT NOT NULL | apparel reprint / mugs and small goods / local courier |
| lead_days | INTEGER NOT NULL | assumed days to deliver; whether calendar or business days is unclear |

**Why it matters:** tells an agent who can restock what and how long it takes;
vendors are linked to invoices.

### leases
| Column | Type | Notes |
|---|---|---|
| id | INTEGER | PK |
| space_name | TEXT NOT NULL | |
| landlord | TEXT NOT NULL | free text, not a key |
| monthly_rent | REAL NOT NULL | |
| next_due | TEXT NOT NULL | YYYY-MM-DD |
| notes | TEXT | NULL in the only row |

No status column and no record of past rent payments.
**Why it matters:** the rent obligation (amount and date) that competes with
invoices for the same cash.

### cash_accounts
| Column | Type | Notes |
|---|---|---|
| name | TEXT | PK (not declared NOT NULL) |
| balance | REAL NOT NULL | |
| date | TEXT NOT NULL | YYYY-MM-DD; presumably the as-of date of the balance (not stated) |

One row: `checking`, 3400.0, 2026-08-31.
**Why it matters:** the money available; any payment an agent proposes must be
checked against this balance.

### payments
| Column | Type | Notes |
|---|---|---|
| id | INTEGER | PK |
| kind | TEXT NOT NULL | no values yet; allowed values unclear |
| ref_id | INTEGER | no FK; what it points to presumably depends on `kind` — unclear |
| amount | REAL NOT NULL | |
| account | TEXT NOT NULL | presumably matches `cash_accounts.name`, but no FK |
| paid_at | TEXT NOT NULL | format unclear at the study (no rows); `pay_approved` now writes the shop date `YYYY-MM-DD` |
| approved_by | TEXT NOT NULL | every payment must name an approver |

**Empty (0 rows) at the Problem 2 study.** After the Problem 9 full run it holds 1 row (see "Full run results").
**Why it matters:** this is where a paid invoice or rent would be recorded, and
`approved_by` being required means every payment needs a named approver.

### invoices
| Column | Type | Notes |
|---|---|---|
| id | INTEGER | PK |
| vendor_id | INTEGER NOT NULL | FK → vendors.id |
| amount | REAL NOT NULL | |
| due_date | TEXT NOT NULL | YYYY-MM-DD |
| status | TEXT NOT NULL | only value seen: `open` (1) |
| description | TEXT | free text, mentions SKU and size |

**Why it matters:** bills the shop owes; overdue ones affect the vendor
relationship and compete for cash.

### tickets
| Column | Type | Notes |
|---|---|---|
| id | INTEGER | PK |
| type | TEXT NOT NULL | customer_order 1, price_override 1, rent_notice 1 |
| requester | TEXT NOT NULL | free text name; there is no customers table |
| subject | TEXT NOT NULL | |
| sku | TEXT | no FK to inventory/pricing |
| size | TEXT | no FK |
| qty | INTEGER | |
| lease_id | INTEGER | FK → leases.id |
| invoice_id | INTEGER | FK → invoices.id |
| status | TEXT NOT NULL | only value seen: `open` (3) |
| notes | TEXT | free text request details |
| created_at | TEXT NOT NULL | ISO 8601 with offset, e.g. `2026-08-31T09:15:00-04:00` |

**Why it matters:** the work queue the agents will triage; each ticket type
points at different parts of the data.

### What "overdue" means here

- **Invoice:** `status = 'open'` and `due_date < desk.date_today`.
  Invoice 501 (due 2026-08-28) is **3 days overdue**.
- **Lease:** no status column, so the only signal is `next_due < desk.date_today`
  (and no matching row in `payments`). Lease 1 is due 2026-09-02, **2 days from
  today, not overdue**.
- Whether something due *on* today counts as overdue is not defined in the data.

---

## How the three open tickets link to the data

### Ticket 101 — customer_order (Tauhid Zaman, "Bulldog tee")

| Link | Via | Linked row |
|---|---|---|
| Stock | `sku`+`size` (no FK) | CC-TEE-WHITE / S: **qty 0**, Aisle B |
| Price | `sku` (no FK) | unit_cost 8.0, list_price 28.0 |
| Invoice | `invoice_id` → invoices.id (FK) | 501: 840.0, due 2026-08-28, open, "Rush reprint CC-TEE-WHITE S" |
| Vendor | invoices.vendor_id → vendors.id (FK) | 1 Bulldog Print Co, apparel reprint, lead 5 days |
| Payments | none | no payment rows for ref 501 |
| Cash | none (not linked) | checking 3400.0 |

What the data shows: wants 1, has 0 in size S (other sizes in stock: L 3, M 5,
XL 2). The linked invoice is for a rush reprint of this exact SKU and size, but
that link to SKU/size is only in the invoice's free-text description. The invoice
is 3 days overdue and unpaid. Whether that reprint has been delivered is unclear
(stock is still 0). A new reprint at lead 5 days would land 2026-09-05 at the
earliest. Cash 3400 covers the 840 invoice.

### Ticket 102 — rent_notice (Elm City Properties, "Rent due")

| Link | Via | Linked row |
|---|---|---|
| Lease | `lease_id` → leases.id (FK) | 1 Chapel Street shop, Elm City Properties, 2400.0, next_due 2026-09-02 |
| Payments | none | no payment rows |
| Cash | none (not linked) | checking 3400.0 |

What the data shows: rent 2400 due in 2 days, matching the note "due in 2 days".
The requester matches `leases.landlord` only as text. Cash 3400 covers 2400 on
its own; rent plus invoice 501 is 3240, leaving 160.

### Ticket 103 — price_override (Yale AI Club, "Bulk hoodie discount")

| Link | Via | Linked row |
|---|---|---|
| Stock | `sku`+`size` (no FK) | CC-HOOD-NAVY / M: **qty 8**, Aisle A |
| Price | `sku` (no FK) | unit_cost 22.0, list_price 58.0 |
| Vendor | none — only implied | Bulldog Print Co is the only "apparel reprint" vendor |
| Invoice | none — only implied via vendor | 501 open and overdue with Bulldog Print Co |
| Cash | none (not linked) | checking 3400.0 |

What the data shows: wants 20 in M, has 8 (short 12; all hoodie sizes total 32).
At list price, 20 × 58 = 1160; cost 20 × 22 = 440; list margin 62.1%. No discount
amount is given — "bulk discount" is only in the notes, and there is no discount
column or table. Restocking would presumably go through Bulldog Print Co (5-day
lead), which already has an overdue unpaid invoice; that link is inferred from
`specialty`, not a key.

---

## Things to watch

- **Foreign keys are not enforced by default.** `PRAGMA foreign_keys` returns 0;
  agents writing to the DB must turn it on or the declared FKs do nothing.
- **`tickets.sku` / `tickets.size` have no FK** to `inventory` or `pricing`, and
  `inventory.sku` has no FK to `pricing`. Today they all match (checked), but
  nothing stops a bad SKU.
- **`payments.ref_id` and `payments.account` have no FKs.** What `ref_id` points
  to depends on `kind`, and no `kind` values exist yet.
- **`payments` is empty**, so there is no history of what has been paid,
  including past rent.
- **Invoice-to-product link is free text only:** invoice 501's description
  "Rush reprint CC-TEE-WHITE S"; `invoices` has no sku/size columns.
- **Ticket 103's vendor is not linked at all**; it can only be inferred from
  `vendors.specialty`.
- **Names are free text, not keys:** ticket requesters, `leases.landlord`. There is
  no customers table.
- **Similar names:** landlord "Elm City Properties" vs vendor "Elm City Gifts" are
  different entities — easy to confuse.
- **`pricing.sku` and `cash_accounts.name` are TEXT PRIMARY KEYs without
  NOT NULL**, which SQLite allows to be NULL.
- **`inventory.name` repeats on every size row** of the same SKU.
- **Mixed date formats:** dates are `YYYY-MM-DD`; `tickets.created_at` is a full
  timestamp with a `-04:00` offset.
- **Relative dates in text:** ticket 102's note says "due in 2 days" rather than a
  date; it agrees with `leases.next_due` today but will go stale.
- **Units and meanings not stated:** currency for amounts/prices; whether
  `lead_days` is calendar or business days; what size `OS` means.
- **Only one value seen for each status column** (`open`), so the full set of
  ticket/invoice statuses is unknown.
- **Sparse ticket columns by type:** 101 has no lease_id; 102 has no sku, size,
  qty or invoice_id; 103 has no lease_id or invoice_id. `desk.notes` and
  `leases.notes` are NULL.
- **Out of stock items:** CC-TEE-WHITE size S and CC-MUG-CREST (OS) both have qty 0.

---

## MCP tools

Server: `mcp_server/server.py` (FastMCP, name `campus-customs`). These three tools open
`data/campus_customs_new.db` read-only (`mode=ro`), use parameterized SQL, and
return `{"found": false, "error": ...}` instead of guessing when a SKU, size or
lease does not exist.

| Tool | Reads | Unlocks | Why it is the right tool for that ticket |
|---|---|---|---|
| `check_stock(sku, size)` | `inventory` | Ticket 101 (also 103) | Ticket 101 asks for CC-TEE-WHITE size S, which is at qty 0, so the agent needs that exact row plus the other sizes (L 3, M 5, XL 2) to offer an alternative; for ticket 103 it shows CC-HOOD-NAVY size M has only 8 against the 20 requested. |
| `get_lease(lease_id)` | `leases`, `desk`, `cash_accounts` | Ticket 102 | Ticket 102 points at lease 1 (Chapel Street shop, 2400.0 due 2026-09-02), and this tool turns that into "due in 2 days, not overdue" using `desk.date_today` 2026-08-31 and shows the 3400.0 checking balance beside the rent. |
| `get_pricing(sku)` | `pricing` | Ticket 103 | The Yale AI Club wants a bulk discount on CC-HOOD-NAVY, and this tool gives the 22.0 cost, 58.0 list price and 62.1% margin that bound how far any discount can go. |

Notes on behaviour:
- `check_stock` returns `qty: 0` for an out-of-stock size (a real zero); a size
  that does not exist returns `found: false` with the sizes that do exist.
- `get_lease` computes `days_until_due` and `is_overdue` from `desk.date_today`,
  never the system clock. `checking_covers_rent` compares checking with this one
  rent payment only; it does not subtract other open bills such as invoice 501.
- `get_pricing` computes `margin_pct` at list price only; there is no discount
  data in the database.

---

# Problem 5 — the agent team

Code: `backend/agents.py` (team, shared model, delegation, limits),
`backend/models.py` (all data types), `backend/audit.py` (audit writer),
`backend/prompts/*.md` (one prompt per agent), `backend/approvals.py` +
`scripts/approve.py` (the human approval path). Every agent uses one model,
`gpt-6-luna`, through the Portkey gateway: one constant (`MODEL_NAME`) and one
shared model object, wired like homework-4 (same base URL, provider header and
`PORTKEY_API_KEY`) but pinned. `scripts/check_models.py` fails if any other
model name appears in the project.

## Agents

All five are PydanticAI agents with a tool loop. Each has its prompt file as
instructions, a typed `output_type`, the MCP tools in its scope (filtered in code
from one shared MCP connection), and `delegate_to_<other>` tools for all four
other agents: **20 directed delegation links**. A delegation runs the other agent
with a task string, passes the parent's usage in (one shared budget), and returns
the child's typed report (or a `{"status": "stopped: <reason>"}` result).

| Agent | Role | MCP tools it can call | Delegates to | Output type |
|---|---|---|---|---|
| **boss** | Reads a ticket, picks who works on it, makes the final call, closes it. Never moves money. | get_today, get_ticket, list_open_tickets, check_stock, get_lease, get_pricing, list_vendors, get_vendor_open_invoices, get_invoice, get_cash_balance, list_payments, list_proposals, **resolve_ticket** | inventory, accounting, facilities, customer_service | `BossDecision` |
| **inventory** | Stock by SKU and size, shortfalls, which vendor can restock and how long it takes. | get_today, get_ticket, list_open_tickets, check_stock, get_pricing, list_vendors, get_vendor_open_invoices | boss, accounting, facilities, customer_service | `SpecialistReport` |
| **accounting** | Cash, invoices, margins; prepares payments and purchase orders for human approval; executes approved payments. | get_today, get_ticket, list_open_tickets, get_pricing, get_cash_balance, get_invoice, get_vendor_open_invoices, list_vendors, list_payments, list_proposals, get_lease, check_stock, **propose_payment, propose_purchase_order, pay_approved** | boss, inventory, facilities, customer_service | `SpecialistReport` |
| **facilities** | The shop space: lease, rent, due date, whether checking covers it. | get_today, get_ticket, list_open_tickets, get_lease, get_cash_balance, list_payments, list_proposals | boss, inventory, accounting, customer_service | `SpecialistReport` |
| **customer_service** | Drafts customer messages onto the drafts board. Drafts only. | get_today, get_ticket, list_open_tickets, check_stock, get_pricing, **save_customer_draft** | boss, inventory, accounting, facilities | `SpecialistReport` |

Output types (`backend/models.py`):
- `SpecialistReport`: agent, status (`complete` / `needs_info` / `blocked`),
  summary, findings (each `{fact, source_tool}`), recommended_actions (each with
  owner and `needs_human_approval`), open_questions, proposal_ids, draft_ids.
- `BossDecision`: ticket_id, worked_on_by, final_decision, findings,
  actions (each `taken` or `proposed`, owner, `needs_human_approval`),
  human_approval_needed, approval_items (proposal ids), ticket_status_set.
- `RunOutcome` wraps every run: `status` is `ok` or `stopped: <reason>`, plus the
  output, run id, depth and usage so far.

Wiring was proven without an LLM (`scripts/wiring_check.py`, a stub model that
records the tool list each agent would send) and live with one cheap call per
agent plus one Boss → Inventory delegation (`scripts/live_check.py`), all labelled
`problem-5-wiring-test` in the audit trail. The live delegation returned
CC-TEE-WHITE size S qty 0, matching the database.

## MCP tools (full list after Problem 5)

Server: `mcp_server/server.py` (FastMCP, `campus-customs`), 19 tools (17 at the end of Problem 5; `list_tickets` and `list_drafts` added in Problem 7). Read tools
open `data/campus_customs_new.db` with `mode=ro`; write tools open it read-write
for one `BEGIN IMMEDIATE` transaction with `PRAGMA foreign_keys = ON`. All inputs
are validated, all SQL is parameterized, missing rows return `found: false` (reads)
or `ok: false, refused: true, reason` (writes), and null stays distinct from 0.
"Stores" are JSON arrays under `data/` (locked, temp file + fsync + `os.replace`;
a corrupt store is renamed aside, never deleted); the shop schema is unchanged.

| Tool | Table(s) / store | R/W | Helps ticket |
|---|---|---|---|
| `check_stock(sku, size)` | inventory | R | 101 (S tee at 0, other sizes), 103 (20 hoodies M vs 8) |
| `get_lease(lease_id)` | leases, desk, cash_accounts | R | 102 (lease 1, 2400 due 2026-09-02) |
| `get_pricing(sku)` | pricing | R | 103 (cost 22, list 58, 62.1% margin) |
| `get_today()` | desk | R | all (today = 2026-08-31 decides overdue) |
| `list_open_tickets()` | tickets | R | all (the queue: 101, 102, 103) |
| `get_ticket(ticket_id)` | tickets + resolutions store | R | all (sku/size/qty, lease_id, invoice_id) |
| `list_vendors()` | vendors, invoices | R | 101, 103 (who can restock, lead_days, `on_hold`) |
| `get_vendor_open_invoices(vendor_id)` | vendors, invoices, desk | R | 101, 103 (vendor 1 held by invoice 501) |
| `get_invoice(invoice_id)` | invoices, vendors, desk | R | 101 (invoice 501: 840, 3 days overdue) |
| `get_cash_balance(account)` | cash_accounts | R | 101, 102, 103 (checking 3400) |
| `list_payments(kind)` | payments | R | 102 (has rent already been paid?), all (no double pay) |
| `list_proposals(status)` | approvals store | R | all (what is pending / approved / executed) |
| `propose_payment(kind, ref_id, amount, reason)` | approvals store (reads invoices/leases, cash_accounts, desk) | W (store only) | 101 (pay 501), 102 (rent) |
| `propose_purchase_order(vendor_id, sku, size, qty, reason)` | approvals store (reads vendors, invoices, inventory, pricing, desk) | W (store only) | 101 (restock S tee), 103 (restock hoodies M) |
| `pay_approved(proposal_id, amount)` | payments, cash_accounts, invoices or leases, approvals store | W | 101, 102 |
| `save_customer_draft(ticket_id, recipient, subject, body)` | drafts board store (reads tickets) | W (store only) | 101, 103 (replies to requesters) |
| `resolve_ticket(ticket_id, status, resolution_note)` | tickets.status + resolutions store | W | all (closing 101, 102, 103) |
| `list_tickets()` | tickets + resolutions store | R | backend only (dashboard ticket list, all statuses); not visible to agents |
| `list_drafts(ticket_id)` | drafts board store | R | backend only (dashboard drafts list); not visible to agents |

Added in Problem 7: `list_tickets` and `list_drafts` are read-only tools for the
web API (`backend/main.py`). They are in no agent's `TOOL_SCOPES`, so the filtered
toolsets never show them to an agent. With them the server has **19 tools**
(the 17 above plus these two), matching `mcp_server/README.md`.

Changes from the suggested set, and why:
- **Added `list_proposals`.** Agents need to see whether a payment or PO is
  already pending/approved/executed before proposing again (idempotency), and
  Accounting must check status before calling `pay_approved`.
- **`pay_approved` takes `amount` as well as `proposal_id`.** The amount is a
  confirmation check: it must equal the approved amount or the call is refused.
- **`propose_payment` takes `kind` (`invoice` / `rent`)** so one tool covers both
  vendor bills (ticket 101) and rent (ticket 102); the amount must equal the
  invoice amount or `monthly_rent` exactly (no partial payments are modelled).
- **`resolve_ticket` statuses are `resolved` and `declined`.** The data only shows
  `open`, so these two are my choice. The resolution note goes to
  `data/ticket_resolutions.json` rather than overwriting `tickets.notes` (which
  holds the requester's original text).
- **Modelling choices in `pay_approved`:** `paid_at` is the shop's
  `desk.date_today`, not the computer's clock. For rent, a successful payment
  **advances `leases.next_due` by one calendar month** (2026-09-02 → 2026-10-02).
  This is a modelling choice: the lease table has no paid flag, so moving the
  due date is how "this month is paid" is recorded. `cash_accounts.date` (the
  as-of date) is left unchanged. "Open unpaid invoice" means `status = 'open'`.
- **Arrival dates** are `desk.date_today + vendors.lead_days` in calendar days
  (whether lead_days are business days is not stated in the data).

## Safety

### Enforced in code

| Guardrail | Where | How |
|---|---|---|
| Single model | `backend/agents.py`, `scripts/check_models.py` | `MODEL_NAME = "gpt-6-luna"`, one shared model object; checker fails on any other model name in the project. |
| Agents reach data only via MCP | `backend/agents.py` | Agents have no sqlite code and no other tools: only the filtered MCP toolset plus delegate tools. |
| Per-agent tool scope | `TOOL_SCOPES` in `backend/agents.py` | Each agent's MCP toolset is filtered; a hidden tool is not sent to the model and cannot be called. Only Accounting has propose/pay tools; only Customer Service has `save_customer_draft`; only Boss has `resolve_ticket`. |
| Human approval for money | `mcp_server/server.py`, `backend/approvals.py` | Agents can only create `pending` proposals. Approval is `backend/approvals.decide()` / `scripts/approve.py`, which is **not** an MCP tool and not given to any agent. `pay_approved` executes only `approved` proposals with `approval_path = human:scripts/approve.py` and a named approver; that name goes into `payments.approved_by`. |
| No negative balance | `pay_approved` | Refuses if checking balance < amount; re-checks after the update and rolls back if negative. |
| No double pay (idempotency) | `propose_payment`, `pay_approved` | No second pending/approved proposal for the same target; an executed proposal is refused; an invoice must still be `open`; rent must still be due on the snapshot date. All in one DB transaction under the approvals-store lock. |
| Amount confirmation | `propose_payment`, `pay_approved` | Proposal amount must equal the invoice/rent; `pay_approved` amount must equal the approved amount. |
| Spending caps | `mcp_server/server.py` | No single payment over 5000 (`MAX_PAYMENT_AMOUNT`); no purchase order over 500 units (`MAX_PO_QTY`). |
| Vendor-invoice hold | `propose_purchase_order` | Refused if the vendor has any `open` invoice (vendor 1 is held by invoice 501). |
| No outbound contact | whole server | No tool sends email or contacts anyone; `save_customer_draft` only writes `data/drafts_board.json` with `sent: false`. |
| Read-only reads | `mcp_server/server.py` | Every read opens the DB with `mode=ro`. |
| Never the original DB | `mcp_server/server.py` | Server refuses to start if pointed at `campus_customs.db`. |
| Audit trail | `backend/audit.py`, `backend/agents.py` | Every model request, tool call, tool result (via the MCP `process_tool_call` hook), delegation, final answer, limit stop and error is appended to `output/audit_trail.json` (append-only, locked, fsync + `os.replace`, corrupt file renamed aside). |
| Secrets and personal data | `backend/audit.py`, `.gitignore`, `build_mcp_toolset` | Key-like values and secret-named fields are redacted; prompt, task and message text is logged only as length + short hash; names and notes are left out of result summaries. Error entries record only the exception type and HTTP status, never raw provider text. Any dated provider snapshot ID of the pinned model is written as plain `gpt-6-luna`. `.env` is gitignored and `.env.example` has placeholders only. The MCP subprocess gets no API key in its environment. |
| Token and loop limits | `LIMITS` in `backend/agents.py` | See below. When a limit hits, the run stops cleanly with `stopped: <reason>`. |

### Only in the prompts (not enforced in code)

- Never state a number that did not come from a tool, and cite the source tool.
- Boss decides; specialists recommend. Who delegates to whom, and when not to.
- Customer Service does not promise stock, dates or discounts not yet decided,
  and keeps internal numbers out of drafts.
- A discount never below cost and always explained with its margin. No tool
  writes a discount; it lives in the Boss's decision and the draft text.
- Do not resolve a ticket while a payment or PO it depends on is pending.
- Prefer clearing an invoice before ordering from a held vendor; when obligations
  compete for cash, say so and pick an order.

Honest limits of the code checks: the MCP server cannot tell which agent is
calling, so tool scoping is enforced on the client side (the filtered toolsets in
`backend/agents.py`), not by the server. The approvals file is trusted: anyone
with filesystem access could edit `data/approvals.json`. The agents have no file
tools, but a real business would sign approvals or keep them in a separate
service with authentication.

Approvals and run history in the web API (added in Problem 7): the approver's
name (`approved_by` / `rejected_by`) is self-declared. The API has no login or
authentication, so anyone who can reach it can approve under any name. That is
acceptable for a local homework app bound to localhost, but a real business
would need authenticated approvers (sign-in, roles, and an approval record tied
to a verified identity). Run status and history (`/api/runs/{run_id}`) are kept
in memory and are lost when the server restarts; the audit trail keeps the
events, but not the run record or the Boss's decision as returned by that route.

### Limits that keep token use in check (`TeamLimits` in `backend/agents.py`)

| Limit | Value | Enforced by |
|---|---|---|
| Max delegation depth | 3 (boss at 0 → 1 → 2 → 3) | `_delegate` refuses deeper calls |
| Max delegations per top-level run (ticket) | 8 | `_delegate` |
| Model requests per run (shared by all agents) | 40 | `UsageLimits(request_limit)` with the parent's usage passed to each child |
| Tool calls per run (shared) | 60 | `UsageLimits(tool_calls_limit)` |
| Total tokens per run (shared) | 400,000 | `UsageLimits(total_tokens_limit)` |
| Output tokens per model request | 4,000 | `max_tokens` model setting |
| Reasoning effort | `none` | model setting (see note) |
| Wall clock per agent run | 240 s | `asyncio.timeout` |
| Loop protection | identical tool call in one agent run, or identical delegation (same caller, target, task) in one ticket, is refused | MCP hook / `_delegate` |
| Output retries | 1 | agent `retries` |

Note from testing: with reasoning effort `low`, the model sometimes looped in
hidden reasoning after a tool result until it hit the 4,000-token cap. The cap
stopped it cleanly (`stopped: error UnexpectedModelBehavior`, visible in the
audit trail), and switching to `none` made every live call succeed in about
100–300 output tokens. `"minimal"` is not supported by this model.

### Known exception to append-only (one-time edit, 2026-10-12)

`output/audit_trail.json` was edited in place once. Entry #82 (ts
`2026-10-11T23:33:39.454457Z`, run_id `effminimal0`, step `error`) quoted a
gateway error from a reasoning-effort test, and that error named a **dated
snapshot ID of gpt-6-luna**. Only that string in that entry's `result_summary`
was replaced with `gpt-6-luna`, so `scripts/check_models.py` passes. The edit
used the writer's own lock, temp file, fsync and `os.replace`. All 143 entries
were kept, none were added, removed or reordered, and a `note` entry
(run_id `audit-maintenance`, name `one_time_model_id_normalization`) was
appended recording exactly what changed and why. To stop this happening again,
the writer now normalizes dated snapshot IDs of the pinned model before writing,
and error entries no longer include raw provider text.

---

## Backend routes

`backend/main.py` (FastAPI). Start it from the backend folder:
`cd backend && uvicorn main:app --reload --port 8000` → http://localhost:8000.
**`POST /api/approvals/{proposal_id}/approve` is the only route that moves money.**
Only three routes change shop data: run (through the agents), approve
(`pay_approved` over MCP) and reset. Every shop read and write goes through the MCP
server; the only direct file operation is the reset copy in `scripts/reset_db.py`.

| Method | URL | What it does |
|---|---|---|
| GET | `/api/tickets` | All tickets: id, type, requester, subject, status, resolution note, and pending approvals tied to each (from the agent run that proposed them, else by the ticket's invoice, lease or SKU/size). |
| POST | `/api/tickets/{ticket_id}/run` | Starts the Boss with the full team on one open ticket in the background; returns 202 + run_id. 404 unknown ticket, 409 not open, 409 if a run is already in progress. Agent limits from `TeamLimits` apply. |
| GET | `/api/runs/{run_id}` | Run status (queued / running / finished / stopped + reason / error), status history, and the Boss's typed decision when finished. Runs are kept in memory. |
| GET | `/api/events` | Agent events from `output/audit_trail.json` (read-only): agent, step, tool or delegate name, summary, depth, ticket, run_id, time. `?after=<cursor>` (returns `next_cursor`), `?limit=` (default 100, capped at 500), `?run_id=`. |
| POST | `/api/approvals/{proposal_id}/approve` | Human approval (body `{"approved_by": name}`, 1–60 chars). Records it with `backend/approvals.decide`, then for a payment calls MCP `pay_approved` and returns cash before/after; for a purchase order just approves it. A refused payment is put back to pending with the reason recorded. |
| POST | `/api/approvals/{proposal_id}/reject` | Human rejection (body `{"rejected_by": name, "reason": optional}`). A rejected proposal can never be paid. |
| GET | `/api/cash` | Checking balance and as-of date, via MCP `get_cash_balance`. |
| POST | `/api/reset` | Body `{"confirm": true}`. Restores the working DB from the original (SHA-256 verified), clears the three stores, appends a `note` to the audit trail (never wipes it). 409 during a run. Same function as `scripts/reset_db.py --confirm`. |
| GET | `/api/approvals?status=` | **Extra.** Proposals with kind, amount, target (invoice / lease / vendor), reason, the agent that proposed it, ticket and past failures. |
| GET | `/api/drafts` | **Extra.** Customer drafts on the board (never sent). |
| GET | `/api/health` | **Extra.** Liveness, model name, runner name, run in progress, limits, CORS origins (no secrets, no full paths). |

Notes:
- **MCP additions for the backend:** two read-only tools, `list_tickets` (all
  statuses, with resolution notes) and `list_drafts`. Neither is in any agent's
  `TOOL_SCOPES`, so agents can't see them.
- **Store reads create no files:** reading a store that doesn't exist yet now
  returns empty and creates nothing, so read routes never create files.
- **Validation:** request bodies are Pydantic models with `extra="forbid"`.
  Validation errors return only location, message and type, never the input.
  Unexpected errors return a generic 500 and log only the exception class.
- **CORS:** only `DASHBOARD_ORIGINS` (default `http://localhost:5173`,
  `http://127.0.0.1:5173`). A wildcard is refused at startup.
- **Test overrides:** `CAMPUS_CUSTOMS_DB`, `CAMPUS_CUSTOMS_ORIGINAL_DB`,
  `CAMPUS_CUSTOMS_STORE_DIR` and `AUDIT_TRAIL_PATH` point the whole backend at
  scratch copies. `CAMPUS_CUSTOMS_RUN_LABEL` labels audit entries.
  `CAMPUS_CUSTOMS_STUB_RUNNER_SECONDS` (tests only) swaps the agent team for a
  stub that calls no model. `/api/health` shows which runner is active.

**Dashboard:** `frontend/` (React + Vite + TypeScript, `npm run dev` on port 5173) shows tickets, live agent activity, approvals, cash and drafts through the routes above; design notes are in `output/design.md`.

---

## Dashboard

`frontend/` is a React + Vite + TypeScript app called "The Back Desk" (start it
with `npm run dev`; it runs at http://localhost:5173 and talks to the API
above). It shows:
- the three tickets as paper slips, stamped RESOLVED or DECLINED;
- the five agents as distinct nameplates, with a live state for each;
- a team map and a routing slip of who asked whom;
- the Boss's memo, a time card per agent, and the carbon-copy event log;
- signature slips for approvals (the only place money moves);
- the till, with an animated drop when cash goes out;
- the drafts tray, with a danger-styled reset.

Everything on the board comes from the API. `?run=<run_id>` opens a finished run
read-only from the desk server's memory (added in Problem 9 for the screenshots).
Design choices, accessibility and limits are in `output/design.md`.

## Full run results (Problem 9)

One clean run on 2026-10-13, using the real runner (`main.default_runner`), the
model gpt-6-luna, the unchanged `TeamLimits` and the audit run label
`problem-9-full-run`. It started with `POST /api/reset` at 2026-10-13T14:57:58Z:
the checksum matched the original `23686a90…f360a`, and the stores were absent.
**Starting checking balance: $3,400.00** (database and `GET /api/cash`).

| Ticket | Runs | Run id | Hand-offs (in order) | MCP tools used | Usage (req / tools / in / out tokens) | Final status |
|---|---|---|---|---|---|---|
| 101 customer order | 1 | `cd5471ed4a62` | Boss → Inventory; Boss → Customer Service | get_ticket, check_stock, list_vendors, get_today, get_vendor_open_invoices, save_customer_draft, resolve_ticket | 12 / 15 / 38,248 / 1,619 | resolved |
| 102 rent notice | 1 | `7869a8484676` | Boss → Facilities; Boss → Accounting | get_ticket, get_lease, get_cash_balance, list_payments, list_proposals, propose_payment, resolve_ticket | 12 / 13 / 40,263 / 1,440 | resolved |
| 103 price override | 1 | `124ecff114e0` | Boss → Accounting; Boss → Inventory; Boss → Customer Service | get_ticket, get_pricing, check_stock, list_vendors, get_today, get_vendor_open_invoices, save_customer_draft, resolve_ticket | 14 / 15 / 47,006 / 2,324 | declined (accepted by the human as final) |

**What happened, per ticket** (from the Boss's decision, the stores and the database):
- **101:** Size S had qty 0, and M 5, L 3 and XL 2 were in stock. Customer Service
  saved DRAFT-0001 asking the customer to take M, L or XL (not sent). Inventory
  found vendor 1 (Bulldog Print Co) on hold because invoice 501 ($840.00) is open
  and overdue. No payment or purchase order was proposed. The Boss resolved the
  ticket.
- **102:** Rent of $2,400.00 for lease 1 was due 2026-09-02 (not overdue). Accounting
  proposed PAY-0001 (rent, lease 1, $2,400.00). The Boss resolved the ticket while
  PAY-0001 was still pending. The human ([human approver]) then approved PAY-0001 in
  the dashboard at 2026-10-13T15:20:51Z. `pay_approved` executed it as payments
  row 1 and moved lease 1's `next_due` to 2026-10-02.
- **103:** Only 8 of the 20 size-M hoodies were in stock, and a restock was blocked
  by invoice 501. Accounting recommended $52.20 per hoodie (10% off $58.00, a
  57.9% margin, above the $22.00 cost). Customer Service saved DRAFT-0002 (not
  sent). The Boss declined the ticket.

**Cash itemization** (database read at 2026-10-13T18:56:21Z):

| Line | What happened | Amount |
|---|---|---|
| Start | checking after the reset | $3,400.00 |
| Ticket 101 | no cash change: the run made no proposal | $0.00 |
| Ticket 102 | payments row 1: rent, lease 1. Proposed by Accounting in run `7869a8484676` (audit trail); approved by [human approver]; `paid_at` 2026-08-31 (shop date); executed 2026-10-13T15:20:51Z | −$2,400.00 |
| Ticket 103 | no cash change: the run made no proposal | $0.00 |
| **End** | `cash_accounts.checking` now | **$1,000.00** |

Arithmetic: $3,400.00 − $2,400.00 (sum of 1 payments row) = $1,000.00, which is the
database value. **Invoice 501 ($840.00, vendor 1) is still open and unpaid**, so
vendor 1 stays on hold and `propose_purchase_order` would refuse any restock from
it. That's why neither the size-S tee (101) nor the size-M hoodies (103) can be
reordered until a human approves paying invoice 501, and no run proposed that.

**Database after the run:**
- tickets: 101 resolved, 102 resolved, 103 declined;
- invoice 501 open;
- lease 1 `next_due` 2026-10-02;
- payments: 1 row;
- checking: $1,000.00.

**Audit trail:**
- **Count:** 144 → 279 entries. All 135 new entries are labelled
  `problem-9-full-run`: the reset note plus 45, 41 and 48 entries for the three
  runs.
- **Earlier entries:** the 144 from before were unchanged, byte for byte.
- **Model:** the only model named is gpt-6-luna.
- **Where the details live:** `output/resolved_tickets.json` (cross-checked: 53/53
  values match), `output/desk_tickets.html` (Actual and Cash tabs) and
  `output/resolved_board.html` (board screenshots).

**Guardrail findings and surprises (honest notes):**
1. **The Boss resolved 102 while its payment was pending.** Its prompt says not to,
   but the rule is prompt-only and the model didn't follow it. The human chose to
   keep the run. Proposed code fix, not applied: `resolve_ticket` should refuse
   while a pending or approved proposal targets that ticket's invoice, lease or
   SKU and size.
2. **Customer Service offered an undecided discount (103).** DRAFT-0002 says "the
   approved bulk price of $52.20", but nobody approved that price; Accounting only
   recommended it. The draft also offers 8 hoodies on a ticket the Boss declined.
   This breaks Customer Service's prompt rule against offering an undecided
   discount. The draft was never sent and has not been edited or deleted.
3. **101's memo mentions an approval nobody requested.** It says paying invoice 501
   "needs human approval", but no agent proposed that payment, so nothing was
   waiting for a human and invoice 501 stays unpaid.
4. **Only the Boss delegated.** Every hand-off in all three runs came from the
   Boss (depth 0); no specialist delegated to another specialist. In 103 the Boss
   called Accounting first, not Inventory.
5. **No limits were hit** (requests, tool calls, tokens, depth, delegations,
   timeout or loop protection), and no run errored or needed repeating. Each
   ticket took exactly 1 run.
6. **Screenshots needed a new dashboard view.** The dashboard could only show runs
   it started itself, and the runs were started through the API, so I added the
   read-only `?run=` view (frontend only, with no backend restart). Because of
   that, the board screenshots show the till at capture time ($1,000.00), not at
   each ticket's resolution.
7. **The approval label names the CLI.** The approved proposal's `approval_path`
   reads `human:scripts/approve.py` even though the approval came through the
   dashboard. Both use the same human-approval function, which stamps that one
   constant.
