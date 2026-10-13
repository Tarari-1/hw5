"""Campus Customs MCP server: the only way the shop's agents reach shop data.

Read tools open the database read-only (mode=ro). The few write tools open it
read-write inside one short transaction, and money only moves through
pay_approved, which requires a proposal a human approved outside MCP.
"""

import calendar
import os
import sqlite3
import sys
from contextlib import closing
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mcp_server import stores  # noqa: E402

# The one database this server talks to: the working copy, never the original.
# CAMPUS_CUSTOMS_DB overrides it only so tests can point at a scratch copy.
DB_PATH = Path(os.environ.get("CAMPUS_CUSTOMS_DB") or PROJECT_ROOT / "data" / "campus_customs_new.db").resolve()

if DB_PATH.name == "campus_customs.db":
    raise RuntimeError("The MCP server must never point at the original campus_customs.db.")

# Hard caps enforced in code (see harness.md "Safety").
MAX_PAYMENT_AMOUNT = 5000.0  # no single proposal or payment above this
MAX_PO_QTY = 500  # no single purchase order above this many units
PAYMENT_ACCOUNT = "checking"

mcp = FastMCP("campus-customs")


def _connect() -> sqlite3.Connection:
    """Open the working copy in SQLite read-only mode."""
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DB_PATH}")
    conn = sqlite3.connect(f"{DB_PATH.as_uri()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _connect_rw() -> sqlite3.Connection:
    """Open the working copy read-write for one explicit transaction (write tools only)."""
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DB_PATH}")
    conn = sqlite3.connect(f"{DB_PATH.as_uri()}?mode=rw", uri=True, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _today(conn: sqlite3.Connection) -> str | None:
    row = conn.execute("SELECT date_today FROM desk").fetchone()
    return row["date_today"] if row else None


def _clean_amount(value: Any, field: str) -> float:
    """Return a positive amount rounded to cents or raise ValueError."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise ValueError(f"{field} must be a positive number.")
    return round(float(value), 2)


def _clean_short(value: Any, field: str, limit: int) -> str:
    text = _clean_text(value, field)
    if len(text) > limit:
        raise ValueError(f"{field} must be at most {limit} characters.")
    return text


def _add_one_month(iso_day: str) -> str:
    d = date.fromisoformat(iso_day)
    year, month = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day).isoformat()


def _refused(reason: str, **extra: Any) -> dict[str, Any]:
    return {"ok": False, "refused": True, "reason": reason, **extra}


def _clean_text(value: Any, field: str) -> str:
    """Return a stripped non-empty string or raise ValueError."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string.")
    return value.strip()


def _clean_id(value: Any, field: str) -> int:
    """Return a positive integer id or raise ValueError (bools are rejected)."""
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field} must be a positive integer.")
    return value


def check_stock(sku: str, size: str) -> dict[str, Any]:
    """Look up stock for one SKU and size, plus every size of that SKU.

    Reads: inventory.
    Returns {"found": true, "sku", "size", "name", "qty", "location",
    "all_sizes": [{"size", "qty", "location"}, ...]}.
    qty 0 means out of stock (a real zero, not unknown).
    If the SKU does not exist, or the size does not exist for that SKU, returns
    {"found": false, "error": ...}; for a missing size, "all_sizes" lists the
    sizes that do exist. Invalid input returns {"found": false, "error": ...}.
    """
    try:
        sku = _clean_text(sku, "sku")
        size = _clean_text(size, "size")
    except ValueError as exc:
        return {"found": False, "error": str(exc)}

    with closing(_connect()) as conn:
        all_rows = conn.execute(
            "SELECT size, qty, location FROM inventory WHERE sku = ? ORDER BY size",
            (sku,),
        ).fetchall()
        row = conn.execute(
            "SELECT sku, size, name, qty, location FROM inventory WHERE sku = ? AND size = ?",
            (sku, size),
        ).fetchone()

    all_sizes = [dict(r) for r in all_rows]
    if not all_rows:
        return {"found": False, "error": f"No inventory rows for SKU {sku!r}."}
    if row is None:
        return {
            "found": False,
            "error": f"SKU {sku!r} has no size {size!r}.",
            "sku": sku,
            "all_sizes": all_sizes,
        }
    return {"found": True, **dict(row), "all_sizes": all_sizes}


def get_lease(lease_id: int) -> dict[str, Any]:
    """Look up a lease and whether its rent is due, overdue and covered by cash.

    Reads: leases, desk (date_today), cash_accounts (the 'checking' row).
    Returns {"found": true, "id", "space_name", "landlord", "monthly_rent",
    "next_due", "notes", "today", "days_until_due", "is_overdue",
    "checking_balance", "checking_as_of", "checking_covers_rent"}.
    "today" is desk.date_today, never the computer's clock. days_until_due is
    negative when past due; is_overdue is true only when next_due is before today.
    checking_covers_rent compares the checking balance with this one rent
    payment only (not other bills). If there is no checking account row, the
    checking fields are null. Missing lease returns {"found": false, "error": ...}.
    """
    try:
        lease_id = _clean_id(lease_id, "lease_id")
    except ValueError as exc:
        return {"found": False, "error": str(exc)}

    with closing(_connect()) as conn:
        lease = conn.execute(
            "SELECT id, space_name, landlord, monthly_rent, next_due, notes FROM leases WHERE id = ?",
            (lease_id,),
        ).fetchone()
        desk = conn.execute("SELECT date_today FROM desk").fetchone()
        checking = conn.execute(
            "SELECT balance, date FROM cash_accounts WHERE name = ?",
            ("checking",),
        ).fetchone()

    if lease is None:
        return {"found": False, "error": f"No lease with id {lease_id}."}
    if desk is None:
        return {"found": False, "error": "desk.date_today is missing; cannot compute due dates."}

    today = date.fromisoformat(desk["date_today"])
    days_until_due = (date.fromisoformat(lease["next_due"]) - today).days
    balance = checking["balance"] if checking is not None else None

    return {
        "found": True,
        **dict(lease),
        "today": desk["date_today"],
        "days_until_due": days_until_due,
        "is_overdue": days_until_due < 0,
        "checking_balance": balance,
        "checking_as_of": checking["date"] if checking is not None else None,
        "checking_covers_rent": None if balance is None else balance >= lease["monthly_rent"],
    }


def get_pricing(sku: str) -> dict[str, Any]:
    """Look up cost, list price and margin for one SKU.

    Reads: pricing.
    Returns {"found": true, "sku", "unit_cost", "list_price", "margin_pct"},
    where margin_pct = (list_price - unit_cost) / list_price * 100 at list
    price, rounded to 1 decimal (null if list_price is 0).
    Missing SKU returns {"found": false, "error": ...}.
    """
    try:
        sku = _clean_text(sku, "sku")
    except ValueError as exc:
        return {"found": False, "error": str(exc)}

    with closing(_connect()) as conn:
        row = conn.execute(
            "SELECT sku, unit_cost, list_price FROM pricing WHERE sku = ?",
            (sku,),
        ).fetchone()

    if row is None:
        return {"found": False, "error": f"No pricing row for SKU {sku!r}."}

    list_price = row["list_price"]
    margin_pct = (
        round((list_price - row["unit_cost"]) / list_price * 100, 1) if list_price else None
    )
    return {"found": True, **dict(row), "margin_pct": margin_pct}


# --- read tools added in Problem 5 ---------------------------------------------


def get_today() -> dict[str, Any]:
    """Return the shop's "today" (desk.date_today) and the desk note.

    Reads: desk.
    Returns {"found": true, "today": "YYYY-MM-DD", "notes"}. This date, never the
    computer's clock, decides what is due or overdue.
    """
    with closing(_connect()) as conn:
        row = conn.execute("SELECT date_today, notes FROM desk").fetchone()
    if row is None:
        return {"found": False, "error": "desk has no row; today is unknown."}
    return {"found": True, "today": row["date_today"], "notes": row["notes"]}


def list_open_tickets() -> dict[str, Any]:
    """List every ticket whose status is 'open', oldest first.

    Reads: tickets.
    Returns {"found": true, "count", "tickets": [{"id", "type", "requester",
    "subject", "status", "created_at"}, ...]}. Use get_ticket for the full row.
    """
    with closing(_connect()) as conn:
        rows = conn.execute(
            "SELECT id, type, requester, subject, status, created_at FROM tickets "
            "WHERE status = ? ORDER BY created_at, id",
            ("open",),
        ).fetchall()
    return {"found": True, "count": len(rows), "tickets": [dict(r) for r in rows]}


def get_ticket(ticket_id: int) -> dict[str, Any]:
    """Return one full ticket row, plus its resolution note if it was resolved.

    Reads: tickets, and the ticket_resolutions store.
    Returns {"found": true, "id", "type", "requester", "subject", "sku", "size",
    "qty", "lease_id", "invoice_id", "status", "notes", "created_at",
    "resolution"}. Null columns stay null (e.g. a rent ticket has no sku).
    "resolution" is null until resolve_ticket is used.
    Missing ticket returns {"found": false, "error": ...}.
    """
    try:
        ticket_id = _clean_id(ticket_id, "ticket_id")
    except ValueError as exc:
        return {"found": False, "error": str(exc)}
    with closing(_connect()) as conn:
        row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    if row is None:
        return {"found": False, "error": f"No ticket with id {ticket_id}."}
    notes = [r for r in stores.read_all(stores.RESOLUTIONS) if r.get("ticket_id") == ticket_id]
    return {"found": True, **dict(row), "resolution": notes[-1] if notes else None}


def list_vendors() -> dict[str, Any]:
    """List every vendor with its lead time and whether it is on hold.

    Reads: vendors, invoices.
    Returns {"found": true, "today", "vendors": [{"id", "name", "specialty",
    "lead_days", "open_invoice_ids", "on_hold"}, ...]}. on_hold is true when the
    vendor has any invoice with status 'open' (unpaid); such a vendor will not ship
    new product, and propose_purchase_order refuses it. lead_days comes straight
    from the vendors table (whether calendar or business days is not stated).
    """
    with closing(_connect()) as conn:
        vendors = conn.execute("SELECT id, name, specialty, lead_days FROM vendors ORDER BY id").fetchall()
        open_rows = conn.execute(
            "SELECT id, vendor_id FROM invoices WHERE status = ? ORDER BY id", ("open",)
        ).fetchall()
        today = _today(conn)
    out = []
    for v in vendors:
        ids = [r["id"] for r in open_rows if r["vendor_id"] == v["id"]]
        out.append({**dict(v), "open_invoice_ids": ids, "on_hold": bool(ids)})
    return {"found": True, "today": today, "vendors": out}


def _invoice_view(row: sqlite3.Row, today: str | None) -> dict[str, Any]:
    inv = dict(row)
    if today is None:
        inv.update(days_overdue=None, is_overdue=None)
    else:
        late = (date.fromisoformat(today) - date.fromisoformat(inv["due_date"])).days
        is_open = inv["status"] == "open"
        inv.update(days_overdue=late if is_open and late > 0 else 0, is_overdue=is_open and late > 0)
    return inv


def get_vendor_open_invoices(vendor_id: int) -> dict[str, Any]:
    """Return a vendor and its open (unpaid) invoices, with how overdue each is.

    Reads: vendors, invoices, desk.
    Returns {"found": true, "vendor": {"id", "name", "specialty", "lead_days"},
    "today", "open_invoices": [{"id", "vendor_id", "amount", "due_date", "status",
    "description", "days_overdue", "is_overdue"}, ...], "open_total", "on_hold"}.
    An empty list means the vendor has no open invoice and can ship.
    Missing vendor returns {"found": false, "error": ...}.
    """
    try:
        vendor_id = _clean_id(vendor_id, "vendor_id")
    except ValueError as exc:
        return {"found": False, "error": str(exc)}
    with closing(_connect()) as conn:
        vendor = conn.execute(
            "SELECT id, name, specialty, lead_days FROM vendors WHERE id = ?", (vendor_id,)
        ).fetchone()
        rows = conn.execute(
            "SELECT * FROM invoices WHERE vendor_id = ? AND status = ? ORDER BY due_date, id",
            (vendor_id, "open"),
        ).fetchall()
        today = _today(conn)
    if vendor is None:
        return {"found": False, "error": f"No vendor with id {vendor_id}."}
    invoices = [_invoice_view(r, today) for r in rows]
    return {
        "found": True,
        "vendor": dict(vendor),
        "today": today,
        "open_invoices": invoices,
        "open_total": round(sum(i["amount"] for i in invoices), 2),
        "on_hold": bool(invoices),
    }


def get_invoice(invoice_id: int) -> dict[str, Any]:
    """Return one invoice with its vendor and overdue status.

    Reads: invoices, vendors, desk.
    Returns {"found": true, "id", "vendor_id", "vendor_name", "amount",
    "due_date", "status", "description", "today", "days_overdue", "is_overdue"}.
    is_overdue is true only for an 'open' invoice whose due_date is before today.
    The description is free text; any SKU it mentions is not a real key.
    Missing invoice returns {"found": false, "error": ...}.
    """
    try:
        invoice_id = _clean_id(invoice_id, "invoice_id")
    except ValueError as exc:
        return {"found": False, "error": str(exc)}
    with closing(_connect()) as conn:
        row = conn.execute(
            "SELECT i.*, v.name AS vendor_name FROM invoices i "
            "LEFT JOIN vendors v ON v.id = i.vendor_id WHERE i.id = ?",
            (invoice_id,),
        ).fetchone()
        today = _today(conn)
    if row is None:
        return {"found": False, "error": f"No invoice with id {invoice_id}."}
    return {"found": True, **_invoice_view(row, today), "today": today}


def get_cash_balance(account: str = "checking") -> dict[str, Any]:
    """Return the balance of one cash account and its as-of date.

    Reads: cash_accounts.
    Returns {"found": true, "name", "balance", "date"} where "date" is the
    as-of date stored with the balance. Cash only goes out in this model (no
    revenue is recorded), so this is the most that can be paid.
    Missing account returns {"found": false, "error": ...}.
    """
    try:
        account = _clean_text(account, "account")
    except ValueError as exc:
        return {"found": False, "error": str(exc)}
    with closing(_connect()) as conn:
        row = conn.execute("SELECT name, balance, date FROM cash_accounts WHERE name = ?", (account,)).fetchone()
    if row is None:
        return {"found": False, "error": f"No cash account named {account!r}."}
    return {"found": True, **dict(row)}


def list_payments(kind: str | None = None) -> dict[str, Any]:
    """List recorded payments, newest first, optionally only one kind.

    Reads: payments.
    kind: optional filter, 'invoice' or 'rent' (the kinds pay_approved writes).
    Returns {"found": true, "count", "payments": [{"id", "kind", "ref_id",
    "amount", "account", "paid_at", "approved_by"}, ...]}. An empty list means
    nothing has been paid yet, not that data is missing.
    """
    if kind is not None:
        try:
            kind = _clean_text(kind, "kind")
        except ValueError as exc:
            return {"found": False, "error": str(exc)}
    sql, params = "SELECT * FROM payments", ()
    if kind is not None:
        sql, params = sql + " WHERE kind = ?", (kind,)
    with closing(_connect()) as conn:
        rows = conn.execute(sql + " ORDER BY id DESC", params).fetchall()
    return {"found": True, "count": len(rows), "payments": [dict(r) for r in rows]}


def list_tickets() -> dict[str, Any]:
    """List every ticket (any status) with its resolution note, oldest first.

    Reads: tickets, and the ticket_resolutions store.
    Returns {"found": true, "count", "tickets": [{"id", "type", "requester",
    "subject", "sku", "size", "qty", "lease_id", "invoice_id", "status",
    "created_at", "resolution"}, ...]}. "resolution" is null until resolved.
    Used by the dashboard backend; not given to any agent.
    """
    with closing(_connect()) as conn:
        rows = conn.execute(
            "SELECT id, type, requester, subject, sku, size, qty, lease_id, invoice_id, status, created_at "
            "FROM tickets ORDER BY created_at, id"
        ).fetchall()
    notes: dict[int, dict[str, Any]] = {}
    for r in stores.read_all(stores.RESOLUTIONS):
        notes[r.get("ticket_id")] = r
    return {"found": True, "count": len(rows),
            "tickets": [{**dict(r), "resolution": notes.get(r["id"])} for r in rows]}


def list_drafts(ticket_id: int | None = None) -> dict[str, Any]:
    """List customer drafts saved on the drafts board, newest first.

    Reads: the drafts board store (data/drafts_board.json), not the database.
    ticket_id: optional filter. Drafts are never sent by any tool.
    Returns {"found": true, "count", "drafts": [...]}. Used by the dashboard
    backend; not given to any agent.
    """
    if ticket_id is not None:
        try:
            ticket_id = _clean_id(ticket_id, "ticket_id")
        except ValueError as exc:
            return {"found": False, "error": str(exc)}
    rows = stores.read_all(stores.DRAFTS)
    if ticket_id is not None:
        rows = [r for r in rows if r.get("ticket_id") == ticket_id]
    return {"found": True, "count": len(rows), "drafts": list(reversed(rows))}


def list_proposals(status: str | None = None) -> dict[str, Any]:
    """List payment and purchase-order proposals from the approvals store.

    Reads: the approvals store (data/approvals.json), not the shop database.
    status: optional filter: 'pending', 'approved', 'rejected' or 'executed'.
    Returns {"found": true, "count", "proposals": [...]}. Only a human can move a
    proposal from 'pending' to 'approved'; there is no tool for that.
    """
    if status is not None and status not in ("pending", "approved", "rejected", "executed"):
        return {"found": False, "error": "status must be pending, approved, rejected or executed."}
    rows = stores.read_all(stores.APPROVALS)
    if status is not None:
        rows = [r for r in rows if r.get("status") == status]
    return {"found": True, "count": len(rows), "proposals": rows}


# --- write tools (approvals store, drafts board, tickets) ----------------------


def propose_payment(kind: str, ref_id: int, amount: float, reason: str) -> dict[str, Any]:
    """Propose paying an open invoice or a lease's rent. Moves no money.

    Writes: the approvals store only (a 'pending' record). Reads: invoices or
    leases, cash_accounts, desk.
    kind: 'invoice' (ref_id = invoices.id) or 'rent' (ref_id = leases.id).
    amount must equal the invoice amount or the lease's monthly_rent exactly.
    Refused (with "reason") when: the target does not exist, the invoice is not
    open, the amount does not match, the amount is over the 5000 cap, or a
    pending/approved proposal for the same target already exists.
    Returns {"ok": true, "proposal": {...}} with status 'pending' and
    "cash_covers_now". A human must approve it with scripts/approve.py before
    pay_approved will execute it.
    """
    try:
        if kind not in ("invoice", "rent"):
            raise ValueError("kind must be 'invoice' or 'rent'.")
        ref_id = _clean_id(ref_id, "ref_id")
        amount = _clean_amount(amount, "amount")
        reason = _clean_short(reason, "reason", 300)
    except ValueError as exc:
        return _refused(str(exc))
    if amount > MAX_PAYMENT_AMOUNT:
        return _refused(f"amount {amount} is over the {MAX_PAYMENT_AMOUNT} per-payment cap.")

    with closing(_connect()) as conn:
        today = _today(conn)
        cash = conn.execute("SELECT balance FROM cash_accounts WHERE name = ?", (PAYMENT_ACCOUNT,)).fetchone()
        if kind == "invoice":
            target = conn.execute("SELECT id, vendor_id, amount, due_date, status FROM invoices WHERE id = ?", (ref_id,)).fetchone()
        else:
            target = conn.execute("SELECT id, space_name, monthly_rent, next_due FROM leases WHERE id = ?", (ref_id,)).fetchone()
    if target is None:
        return _refused(f"No {'invoice' if kind == 'invoice' else 'lease'} with id {ref_id}.")
    if kind == "invoice":
        if target["status"] != "open":
            return _refused(f"Invoice {ref_id} is not open (status {target['status']!r}).")
        expected, snapshot = round(target["amount"], 2), {"invoice_due_date": target["due_date"], "vendor_id": target["vendor_id"]}
    else:
        expected, snapshot = round(target["monthly_rent"], 2), {"lease_next_due": target["next_due"]}
    if amount != expected:
        return _refused(f"amount {amount} does not match the {kind} amount {expected}.")
    if cash is None:
        return _refused(f"No {PAYMENT_ACCOUNT!r} cash account.")

    with stores.locked(stores.APPROVALS) as records:
        dup = [r for r in records if r.get("kind") == "payment" and r.get("payment_kind") == kind
               and r.get("ref_id") == ref_id and r.get("status") in ("pending", "approved")]
        if dup:
            return _refused(f"Proposal {dup[0]['id']} for this {kind} is already {dup[0]['status']}.",
                            existing_proposal_id=dup[0]["id"])
        proposal = {
            "id": stores.next_id(records, "PAY"),
            "kind": "payment",
            "payment_kind": kind,
            "ref_id": ref_id,
            "amount": amount,
            "account": PAYMENT_ACCOUNT,
            "reason": reason,
            "target_snapshot": snapshot,
            "shop_today": today,
            "cash_balance_at_proposal": cash["balance"],
            "cash_covers_now": cash["balance"] >= amount,
            "status": "pending",
            "created_at": stores.now_utc(),
            "approved_by": None,
            "approval_path": None,
        }
        records.append(proposal)
    return {"ok": True, "proposal": proposal,
            "next_step": "A human must approve this with scripts/approve.py; no money has moved."}


def propose_purchase_order(vendor_id: int, sku: str, size: str, qty: int, reason: str) -> dict[str, Any]:
    """Propose a restock purchase order. Moves no money and changes no inventory.

    Writes: the approvals store only (a 'pending' record). Reads: vendors,
    invoices, inventory, pricing, desk.
    Refused (with "reason" and the invoice ids) if the vendor has ANY open unpaid
    invoice, because that vendor will not ship. Also refused for an unknown vendor,
    an unknown SKU/size, a SKU without pricing, or qty over 500.
    expected_arrival = desk.date_today + vendors.lead_days (calendar days).
    estimated_cost = qty * pricing.unit_cost.
    Returns {"ok": true, "proposal": {...}} with status 'pending'.
    """
    try:
        vendor_id = _clean_id(vendor_id, "vendor_id")
        sku = _clean_text(sku, "sku")
        size = _clean_text(size, "size")
        qty = _clean_id(qty, "qty")
        reason = _clean_short(reason, "reason", 300)
    except ValueError as exc:
        return _refused(str(exc))
    if qty > MAX_PO_QTY:
        return _refused(f"qty {qty} is over the {MAX_PO_QTY}-unit purchase-order cap.")

    with closing(_connect()) as conn:
        vendor = conn.execute("SELECT id, name, lead_days FROM vendors WHERE id = ?", (vendor_id,)).fetchone()
        open_inv = conn.execute(
            "SELECT id, amount, due_date FROM invoices WHERE vendor_id = ? AND status = ? ORDER BY id",
            (vendor_id, "open"),
        ).fetchall()
        stock = conn.execute("SELECT qty FROM inventory WHERE sku = ? AND size = ?", (sku, size)).fetchone()
        price = conn.execute("SELECT unit_cost FROM pricing WHERE sku = ?", (sku,)).fetchone()
        today = _today(conn)
    if vendor is None:
        return _refused(f"No vendor with id {vendor_id}.")
    if open_inv:
        return _refused(
            f"Vendor {vendor_id} ({vendor['name']}) has open unpaid invoice(s) "
            f"{[r['id'] for r in open_inv]}; it will not ship until they are paid.",
            open_invoices=[dict(r) for r in open_inv],
        )
    if stock is None:
        return _refused(f"No inventory row for SKU {sku!r} size {size!r}.")
    if price is None:
        return _refused(f"No pricing row for SKU {sku!r}; cannot cost the order.")
    if today is None:
        return _refused("desk.date_today is missing; cannot compute arrival.")

    arrival = (date.fromisoformat(today) + timedelta(days=vendor["lead_days"])).isoformat()
    with stores.locked(stores.APPROVALS) as records:
        proposal = {
            "id": stores.next_id(records, "PO"),
            "kind": "purchase_order",
            "vendor_id": vendor_id,
            "vendor_name": vendor["name"],
            "sku": sku,
            "size": size,
            "qty": qty,
            "unit_cost": price["unit_cost"],
            "estimated_cost": round(qty * price["unit_cost"], 2),
            "lead_days": vendor["lead_days"],
            "shop_today": today,
            "expected_arrival": arrival,
            "current_qty": stock["qty"],
            "reason": reason,
            "status": "pending",
            "created_at": stores.now_utc(),
            "approved_by": None,
            "approval_path": None,
        }
        records.append(proposal)
    return {"ok": True, "proposal": proposal,
            "next_step": "A human must approve this purchase order; inventory is unchanged."}


def pay_approved(proposal_id: str, amount: float) -> dict[str, Any]:
    """Execute a payment proposal that a human has already approved.

    Writes: payments (new row), cash_accounts (balance lowered), and invoices
    (status -> 'paid') or leases (next_due advanced one month); then marks the
    proposal 'executed' in the approvals store.
    amount must equal the approved proposal's amount (a confirmation check).
    Refused (with "reason"), and nothing changes, when: the proposal does not
    exist or is a purchase order; it is not 'approved' by the human path; it was
    already executed (no double pay); the amount does not match; the invoice is no
    longer open or the rent was already advanced; or the checking balance is less
    than the amount (no balance may go negative).
    Returns {"ok": true, "payment": {...}, "balance_before", "balance_after"}.
    """
    try:
        proposal_id = _clean_short(proposal_id, "proposal_id", 20)
        amount = _clean_amount(amount, "amount")
    except ValueError as exc:
        return _refused(str(exc))

    with stores.locked(stores.APPROVALS) as records:
        match = [r for r in records if r.get("id") == proposal_id]
        if not match:
            return _refused(f"No proposal with id {proposal_id!r}.")
        p = match[0]
        if p.get("kind") != "payment":
            return _refused(f"{proposal_id} is a {p.get('kind')}, not a payment; pay_approved only pays payments.")
        if p.get("status") == "executed":
            return _refused(f"{proposal_id} was already executed (payment {p.get('payment_id')}); no double pay.")
        if p.get("status") != "approved":
            return _refused(f"{proposal_id} is {p.get('status')!r}, not 'approved'; a human must approve it first.")
        if p.get("approval_path") != stores.HUMAN_APPROVAL_PATH or not p.get("approved_by"):
            return _refused(f"{proposal_id} was not approved through the human approval path.")
        if amount != p["amount"]:
            return _refused(f"amount {amount} does not match the approved amount {p['amount']}.")

        conn = _connect_rw()
        try:
            conn.execute("BEGIN IMMEDIATE")
            today = _today(conn)
            cash = conn.execute("SELECT balance FROM cash_accounts WHERE name = ?", (p["account"],)).fetchone()
            if p["payment_kind"] == "invoice":
                inv = conn.execute("SELECT status FROM invoices WHERE id = ?", (p["ref_id"],)).fetchone()
                if inv is None or inv["status"] != "open":
                    conn.execute("ROLLBACK")
                    return _refused(f"Invoice {p['ref_id']} is not open; nothing paid.")
            else:
                lease = conn.execute("SELECT next_due FROM leases WHERE id = ?", (p["ref_id"],)).fetchone()
                if lease is None or lease["next_due"] != p["target_snapshot"]["lease_next_due"]:
                    conn.execute("ROLLBACK")
                    return _refused(f"Lease {p['ref_id']} rent for {p['target_snapshot']['lease_next_due']} is no longer due; nothing paid.")
            if cash is None or cash["balance"] < amount:
                conn.execute("ROLLBACK")
                return _refused(
                    f"Insufficient cash: {p['account']} has {None if cash is None else cash['balance']}, "
                    f"payment is {amount}; refused so no balance goes negative."
                )
            before = cash["balance"]
            cur = conn.execute(
                "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) VALUES (?, ?, ?, ?, ?, ?)",
                (p["payment_kind"], p["ref_id"], amount, p["account"], today, p["approved_by"]),
            )
            payment_id = cur.lastrowid
            conn.execute("UPDATE cash_accounts SET balance = balance - ? WHERE name = ?", (amount, p["account"]))
            if p["payment_kind"] == "invoice":
                conn.execute("UPDATE invoices SET status = ? WHERE id = ?", ("paid", p["ref_id"]))
                effect = {"invoice_id": p["ref_id"], "invoice_status": "paid"}
            else:
                new_due = _add_one_month(p["target_snapshot"]["lease_next_due"])
                conn.execute("UPDATE leases SET next_due = ? WHERE id = ?", (new_due, p["ref_id"]))
                effect = {"lease_id": p["ref_id"], "next_due_before": p["target_snapshot"]["lease_next_due"], "next_due_after": new_due}
            after = conn.execute("SELECT balance FROM cash_accounts WHERE name = ?", (p["account"],)).fetchone()["balance"]
            if after < 0:  # belt and braces: never commit a negative balance
                conn.execute("ROLLBACK")
                return _refused("Payment would make the balance negative; rolled back.")
            conn.execute("COMMIT")
        except Exception:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

        p.update(status="executed", payment_id=payment_id, executed_at=stores.now_utc())
    return {
        "ok": True,
        "payment": {"id": payment_id, "kind": p["payment_kind"], "ref_id": p["ref_id"], "amount": amount,
                    "account": p["account"], "paid_at": today, "approved_by": p["approved_by"]},
        "effect": effect,
        "balance_before": before,
        "balance_after": after,
        "proposal_id": proposal_id,
    }


def save_customer_draft(ticket_id: int, recipient: str, subject: str, body: str) -> dict[str, Any]:
    """Save a customer message draft on the board. It is NOT sent to anyone.

    Writes: the drafts board store (data/drafts_board.json). Reads: tickets.
    No tool on this server can send email or contact anyone; a human reads the
    board and decides what to send. subject is at most 150 characters and body at
    most 2000. Missing ticket returns {"ok": false, ...}.
    Returns {"ok": true, "draft": {"id", "ticket_id", "recipient", "subject",
    "body", "status": "draft", "sent": false, "created_at"}}.
    """
    try:
        ticket_id = _clean_id(ticket_id, "ticket_id")
        recipient = _clean_short(recipient, "recipient", 100)
        subject = _clean_short(subject, "subject", 150)
        body = _clean_short(body, "body", 2000)
    except ValueError as exc:
        return _refused(str(exc))
    with closing(_connect()) as conn:
        exists = conn.execute("SELECT 1 FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    if exists is None:
        return _refused(f"No ticket with id {ticket_id}.")
    with stores.locked(stores.DRAFTS) as records:
        draft = {"id": stores.next_id(records, "DRAFT"), "ticket_id": ticket_id, "recipient": recipient,
                 "subject": subject, "body": body, "status": "draft", "sent": False,
                 "created_at": stores.now_utc()}
        records.append(draft)
    return {"ok": True, "draft": draft, "note": "Saved on the drafts board only; nothing was sent."}


def resolve_ticket(ticket_id: int, status: str, resolution_note: str) -> dict[str, Any]:
    """Close an open ticket with a final status and a short resolution note.

    Writes: tickets.status, and the note in the ticket_resolutions store.
    status: 'resolved' or 'declined'. resolution_note: at most 500 characters.
    Refused if the ticket does not exist or is not 'open'.
    Only the Boss agent is given this tool (filtered in backend/agents.py).
    Returns {"ok": true, "ticket_id", "status_before", "status_after", "resolution"}.
    """
    try:
        ticket_id = _clean_id(ticket_id, "ticket_id")
        if status not in ("resolved", "declined"):
            raise ValueError("status must be 'resolved' or 'declined'.")
        resolution_note = _clean_short(resolution_note, "resolution_note", 500)
    except ValueError as exc:
        return _refused(str(exc))
    with stores.locked(stores.RESOLUTIONS) as records:
        conn = _connect_rw()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT status FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
            if row is None or row["status"] != "open":
                conn.execute("ROLLBACK")
                return _refused(f"Ticket {ticket_id} {'does not exist' if row is None else 'is not open'}.")
            today = _today(conn)
            conn.execute("UPDATE tickets SET status = ? WHERE id = ?", (status, ticket_id))
            conn.execute("COMMIT")
        except Exception:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()
        note = {"ticket_id": ticket_id, "status": status, "note": resolution_note,
                "shop_today": today, "created_at": stores.now_utc()}
        records.append(note)
    return {"ok": True, "ticket_id": ticket_id, "status_before": "open", "status_after": status, "resolution": note}


READ_TOOLS = (
    check_stock, get_lease, get_pricing, get_today, list_open_tickets, get_ticket,
    list_vendors, get_vendor_open_invoices, get_invoice, get_cash_balance,
    list_payments, list_proposals, list_tickets, list_drafts,
)
WRITE_TOOLS = (propose_payment, propose_purchase_order, pay_approved, save_customer_draft, resolve_ticket)

for _tool in READ_TOOLS + WRITE_TOOLS:
    mcp.tool(_tool)


if __name__ == "__main__":
    mcp.run(show_banner=False)
