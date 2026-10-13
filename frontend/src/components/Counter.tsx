import { useEffect, useId, useRef, useState, type ReactNode } from 'react'
import type { Approval, ApproveResult, Cash, Draft } from '../api'
import { agentTitle } from '../agents'
import { money, moneyDelta } from '../format'

/** A native modal dialog: focus is trapped by the browser and Escape cancels. */
export function Dialog({ open, onClose, title, tone, children }: {
  open: boolean
  onClose: () => void
  title: string
  tone?: 'danger'
  children: ReactNode
}) {
  const ref = useRef<HTMLDialogElement>(null)
  const titleId = useId()
  useEffect(() => {
    const d = ref.current
    if (!d) return
    if (open && !d.open) d.showModal()
    if (!open && d.open) d.close()
  }, [open])
  return (
    <dialog ref={ref} className={`dialog${tone ? ` dialog--${tone}` : ''}`} aria-labelledby={titleId} onClose={onClose}>
      <h2 id={titleId} className="dialog__title">{title}</h2>
      {children}
    </dialog>
  )
}

/** The till: a receipt-paper ledger. A change prints a tape slip showing the drop. */
export function Till({ cash }: { cash: Cash | null }) {
  const prev = useRef<number | null>(null)
  const [tape, setTape] = useState<{ key: number; from: number; to: number } | null>(null)
  useEffect(() => {
    if (!cash) return
    if (prev.current !== null && prev.current !== cash.balance) {
      setTape({ key: Date.now(), from: prev.current, to: cash.balance })
    }
    prev.current = cash.balance
  }, [cash])
  return (
    <section className="till" aria-labelledby="till-h">
      <h2 id="till-h" className="till__head">Till · {cash?.account ?? 'checking'}</h2>
      <p className="till__amount" key={tape?.key ?? 0} data-changed={tape ? 'yes' : 'no'}>
        <span className="sr-only">Balance </span>{money(cash?.balance)}
      </p>
      <p className="till__asof">as of {cash?.as_of ?? '—'} · cash only goes out</p>
      <div aria-live="polite" className="till__tapewrap">
        {tape && (
          <p className={`tape ${tape.to < tape.from ? 'tape--drop' : 'tape--rise'}`} key={tape.key}>
            <span className="tape__delta">{moneyDelta(tape.from, tape.to)}</span>
            <span className="tape__was">was {money(tape.from)}, now {money(tape.to)}</span>
          </p>
        )}
      </div>
    </section>
  )
}

export type SlipResult =
  | { id: string; kind: 'paid'; result: Extract<ApproveResult, { kind: 'payment' }> }
  | { id: string; kind: 'po'; note: string }
  | { id: string; kind: 'refused'; reason: string; status: string | null; note: string }
  | { id: string; kind: 'rejected'; note: string }
  | { id: string; kind: 'error'; message: string }

function plainWhat(a: Approval): string {
  if (a.kind === 'purchase_order') return 'This approves a purchase order; no money moves and stock does not change.'
  return `This will pay ${money(a.amount)} from checking (${a.target}).`
}

/** Signature slips: everything the team prepared that needs a human. */
export function Approvals({ approvals, busy, lastResult, onApprove, onReject }: {
  approvals: Approval[]
  busy: boolean
  lastResult: SlipResult | null
  onApprove: (a: Approval, name: string) => void
  onReject: (a: Approval, name: string, reason: string) => void
}) {
  const [open, setOpen] = useState<{ a: Approval; mode: 'approve' | 'reject' } | null>(null)
  const [name, setName] = useState<string>(() => localStorage.getItem('desk.approverName') ?? '')
  const [reason, setReason] = useState('')
  const nameId = useId()
  const reasonId = useId()
  const trimmed = name.trim()
  const nameOk = trimmed.length >= 1 && trimmed.length <= 60 && /^[A-Za-z][A-Za-z .'-]*$/.test(trimmed)

  function submit() {
    if (!open || !nameOk) return
    localStorage.setItem('desk.approverName', trimmed)
    if (open.mode === 'approve') onApprove(open.a, trimmed)
    else onReject(open.a, trimmed, reason.trim())
    setOpen(null)
    setReason('')
  }

  return (
    <section className="slips" aria-labelledby="slips-h">
      <h2 id="slips-h" className="section-title">Needs a signature <span>{approvals.length} waiting</span></h2>
      {lastResult && <SlipOutcome r={lastResult} />}
      {approvals.length === 0 ? (
        <p className="quiet">Nothing waiting. The team can only propose; payments wait here for a person.</p>
      ) : (
        <ul className="slips__list">
          {approvals.map((a) => (
            <li key={a.id} className={`slip-card slip-card--${a.kind}`}>
              <p className="slip-card__id">{a.id} · {a.kind === 'payment' ? `${a.payment_kind ?? ''} payment` : 'purchase order'}</p>
              <p className="slip-card__amount">{money(a.amount)}</p>
              <dl className="slip-card__facts">
                <dt>For</dt><dd>{a.target}</dd>
                {a.reason && (<><dt>Why</dt><dd>{a.reason}</dd></>)}
                <dt>Proposed by</dt><dd>{agentTitle(a.proposed_by)}</dd>
                {a.ticket_id !== null && (<><dt>Ticket</dt><dd>{a.ticket_id}</dd></>)}
                {a.expected_arrival && (<><dt>Arrives</dt><dd>{a.expected_arrival}</dd></>)}
              </dl>
              {a.failures.length > 0 && (
                <p className="slip-card__fail">Last attempt refused: {a.failures[a.failures.length - 1]?.reason}</p>
              )}
              <div className="slip-card__actions">
                <button type="button" className="btn btn--sign" disabled={busy} onClick={() => setOpen({ a, mode: 'approve' })}>
                  Approve…
                </button>
                <button type="button" className="btn btn--ghost" disabled={busy} onClick={() => setOpen({ a, mode: 'reject' })}>
                  Reject…
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
      <Dialog open={open !== null} onClose={() => setOpen(null)}
        title={open?.mode === 'approve' ? `Sign for ${open.a.id}` : `Reject ${open?.a.id ?? ''}`}>
        {open && (
          <form method="dialog" onSubmit={(e) => { e.preventDefault(); submit() }}>
            <p className="dialog__amount">{money(open.a.amount)}</p>
            <p className="dialog__target">{open.a.target}</p>
            <p className="dialog__what">
              {open.mode === 'approve' ? plainWhat(open.a) : 'This rejects the proposal. It can never be paid afterwards.'}
            </p>
            <label htmlFor={nameId} className="field">Your name (self-declared, remembered in this browser)</label>
            <input id={nameId} className="input" value={name} onChange={(e) => setName(e.target.value)} maxLength={60}
              autoComplete="name" required autoFocus aria-invalid={name !== '' && !nameOk} />
            {name !== '' && !nameOk && <p className="hint">Letters, spaces and . ' - only, up to 60 characters.</p>}
            {open.mode === 'reject' && (
              <>
                <label htmlFor={reasonId} className="field">Reason (optional)</label>
                <input id={reasonId} className="input" value={reason} maxLength={200} onChange={(e) => setReason(e.target.value)} />
              </>
            )}
            <div className="dialog__buttons">
              <button type="button" className="btn btn--ghost" onClick={() => setOpen(null)}>Cancel</button>
              <button type="submit" className={open.mode === 'approve' ? 'btn btn--sign' : 'btn btn--danger'} disabled={!nameOk}>
                {open.mode === 'approve'
                  ? open.a.kind === 'payment' ? `Sign and pay ${money(open.a.amount)}` : 'Sign the purchase order'
                  : 'Reject proposal'}
              </button>
            </div>
          </form>
        )}
      </Dialog>
    </section>
  )
}

function SlipOutcome({ r }: { r: SlipResult }) {
  switch (r.kind) {
    case 'paid':
      return (
        <output className="outcome outcome--ok">
          {r.id} paid by {r.result.approved_by}: {money(r.result.payment.amount)} out of checking. Cash {money(r.result.cash_before)} → {money(r.result.cash_after)}.
        </output>
      )
    case 'po':
      return <output className="outcome outcome--ok">{r.id}: {r.note}</output>
    case 'rejected':
      return <output className="outcome">{r.id}: {r.note}</output>
    case 'refused':
      return (
        <p className="outcome outcome--refused" role="alert">
          {r.id} was refused by the desk server: {r.reason} The proposal is back to {r.status ?? 'pending'}; nothing was paid.
        </p>
      )
    case 'error':
      return <p className="outcome outcome--refused" role="alert">{r.id}: {r.message}</p>
  }
}

/** The drafts tray: what Customer Service wrote. None of it was sent. */
export function Drafts({ drafts }: { drafts: Draft[] }) {
  return (
    <section className="tray" aria-labelledby="tray-h">
      <h2 id="tray-h" className="section-title">Drafts tray <span>draft, never sent</span></h2>
      {drafts.length === 0 ? (
        <p className="quiet">No drafts on the board.</p>
      ) : (
        <ul className="tray__list">
          {drafts.map((d) => (
            <li key={d.id} className="draft">
              <span className="draft__watermark" aria-hidden="true">Draft · not sent</span>
              <p className="draft__meta">{d.id} · ticket {d.ticket_id} · to {d.recipient}</p>
              <p className="draft__subject">{d.subject}</p>
              <p className="draft__body">{d.body}</p>
              <p className="draft__flag">Draft, never sent</p>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
