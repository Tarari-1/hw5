# Campus Customs MCP server

One MCP server (FastMCP, name `campus-customs`) that is the only way the shop's
five agents reach shop data. Read tools open the database read-only (SQLite
`mode=ro`). A few write tools change data, each refusing in code when a shop rule
would be broken. No tool sends email or contacts anyone.

**Database:** `data/campus_customs_new.db` (the working copy), resolved from the
project root by the `DB_PATH` constant in `server.py`. It never uses the original
`data/campus_customs.db` (the server refuses to start if pointed at it).
`CAMPUS_CUSTOMS_DB` overrides the path for tests on a scratch copy.

**Stores** (JSON arrays under `data/`, written with a lock, temp file, fsync and
`os.replace`; see `stores.py`): `approvals.json` (payment and purchase-order
proposals), `drafts_board.json` (customer drafts, never sent),
`ticket_resolutions.json` (resolution notes). `CAMPUS_CUSTOMS_STORE_DIR`
overrides the directory for tests.

## Tools (19)

Read (database opened with `mode=ro`):
- `check_stock(sku, size)`: qty, name and location for one SKU and size, plus the qty of every size of that SKU.
- `get_lease(lease_id)`: the lease row, days until rent is due and an overdue flag (from `desk.date_today`), plus the checking balance.
- `get_pricing(sku)`: unit cost, list price and margin % at list price for one SKU.
- `get_today()`: the shop's today (`desk.date_today`) and desk note.
- `list_open_tickets()`: every ticket with status `open`.
- `get_ticket(ticket_id)`: one full ticket row plus its resolution note, if any.
- `list_vendors()`: vendors with lead_days, open invoice ids and an `on_hold` flag.
- `get_vendor_open_invoices(vendor_id)`: a vendor's open (unpaid) invoices with days overdue.
- `get_invoice(invoice_id)`: one invoice with vendor name and overdue status.
- `get_cash_balance(account="checking")`: balance and as-of date of a cash account.
- `list_payments(kind=None)`: recorded payments, optionally only `invoice` or `rent`.
- `list_proposals(status=None)`: payment and purchase-order proposals from the approvals store.
- `list_tickets()`: every ticket (any status) with its resolution note. Used by the web API; not given to agents.
- `list_drafts(ticket_id=None)`: customer drafts on the drafts board. Used by the web API; not given to agents.

Write:
- `propose_payment(kind, ref_id, amount, reason)`: creates a `pending` payment proposal for an open invoice or a lease's rent; moves no money.
- `propose_purchase_order(vendor_id, sku, size, qty, reason)`: creates a `pending` PO with estimated cost and expected arrival (today + lead_days); refused if the vendor has an open unpaid invoice; changes no inventory.
- `pay_approved(proposal_id, amount)`: executes a human-approved payment (payments row, lower cash, invoice → paid or rent next_due + 1 month); refuses if not approved, already executed, amount mismatched, target not open, or cash short.
- `save_customer_draft(ticket_id, recipient, subject, body)`: saves a draft on the drafts board; nothing is sent.
- `resolve_ticket(ticket_id, status, resolution_note)`: sets an open ticket to `resolved` or `declined` and stores the note.

Human approval is **not** an MCP tool: a person runs
`.venv/bin/python scripts/approve.py approve <proposal_id> --by "Name"`.

## Run

```bash
.venv/bin/pip install -r requirements.txt
.venv/bin/python mcp_server/server.py
```
