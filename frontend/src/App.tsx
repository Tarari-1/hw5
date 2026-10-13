import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  API_BASE, ApiError, ServerUnreachable, api,
  type Approval, type Cash, type DeskEvent, type Draft, type Health, type Run, type Ticket,
} from './api'
import { agentTitle } from './agents'
import { deriveDesk, describeEvent, isRunActive, runIdFromSearch } from './desk'
import { Tickets } from './components/Tickets'
import { Floor } from './components/Floor'
import { CarbonLog, Decision, Summaries } from './components/RunReport'
import { Approvals, Dialog, Drafts, Till, type SlipResult } from './components/Counter'

const FAST_MS = 1000 // during a run
const SLOW_MS = 8000 // otherwise
const ANNOUNCE_GAP_MS = 4000 // the live region speaks at most this often

function usePageVisible(): boolean {
  const [visible, setVisible] = useState(() => document.visibilityState !== 'hidden')
  useEffect(() => {
    const on = () => setVisible(document.visibilityState !== 'hidden')
    document.addEventListener('visibilitychange', on)
    return () => document.removeEventListener('visibilitychange', on)
  }, [])
  return visible
}

function messageOf(e: unknown): string {
  if (e instanceof ApiError || e instanceof ServerUnreachable) return e.message
  return 'Something went wrong talking to the desk server.'
}

function mergeEvents(prev: DeskEvent[], next: DeskEvent[]): DeskEvent[] {
  if (next.length === 0) return prev
  const seen = new Set(prev.map((e) => e.seq))
  return [...prev, ...next.filter((e) => !seen.has(e.seq))].sort((a, b) => a.seq - b.seq)
}

export default function App() {
  const visible = usePageVisible()
  const [server, setServer] = useState<'checking' | 'up' | 'down'>('checking')
  const [health, setHealth] = useState<Health | null>(null)
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [cash, setCash] = useState<Cash | null>(null)
  const [approvals, setApprovals] = useState<Approval[]>([])
  const [drafts, setDrafts] = useState<Draft[]>([])
  const [selected, setSelected] = useState<number | null>(null)
  const [run, setRun] = useState<Run | null>(null)
  const [runEvents, setRunEvents] = useState<DeskEvent[]>([])
  const [recent, setRecent] = useState<DeskEvent[]>([])
  const [starting, setStarting] = useState(false)
  const [startError, setStartError] = useState<string | null>(null)
  const [slipBusy, setSlipBusy] = useState(false)
  const [slipResult, setSlipResult] = useState<SlipResult | null>(null)
  const [resetOpen, setResetOpen] = useState(false)
  const [resetMsg, setResetMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const [announce, setAnnounce] = useState('')
  const [viewing, setViewing] = useState<{ runId: string; error: string | null } | null>(null)

  const deskCursor = useRef<number | null>(null)
  const runCursor = useRef(0)
  const inflight = useRef(false)
  const lastSpoken = useRef(0)

  const noteFailure = useCallback((e: unknown) => {
    if (e instanceof ServerUnreachable) setServer('down')
  }, [])

  const refreshDesk = useCallback(async () => {
    try {
      const [t, c, a, d] = await Promise.all([api.tickets(), api.cash(), api.approvals('pending'), api.drafts()])
      setTickets(t)
      setCash(c)
      setApprovals(a)
      setDrafts(d)
      setServer('up')
      setSelected((s) => s ?? t.find((x) => x.status === 'open')?.id ?? t[0]?.id ?? null)
    } catch (e) {
      noteFailure(e)
    }
  }, [noteFailure])

  const speak = useCallback((text: string, force = false) => {
    const now = Date.now()
    if (!force && now - lastSpoken.current < ANNOUNCE_GAP_MS) return
    lastSpoken.current = now
    setAnnounce(text)
  }, [])

  // ?run=<run_id>: open one finished run read-only (it lives in the server's memory until a restart).
  useEffect(() => {
    const runId = runIdFromSearch(window.location.search)
    if (!runId) return
    let stop = false
    void (async () => {
      try {
        const [r, page] = await Promise.all([api.run(runId), api.events({ runId, after: 0, limit: 500 })])
        if (stop) return
        runCursor.current = page.next_cursor
        setRun(r)
        setRunEvents(page.events)
        setSelected(r.ticket_id)
        setViewing({ runId, error: null })
      } catch (e) {
        noteFailure(e)
        if (!stop) setViewing({ runId, error: messageOf(e) })
      }
    })()
    return () => { stop = true }
  }, [noteFailure])

  // Health: fast retries while down, slow checks while up. Attaches to a run already in progress.
  useEffect(() => {
    if (!visible) return
    let stop = false
    const check = async () => {
      try {
        const h = await api.health()
        if (stop) return
        setHealth(h)
        if (server !== 'up') await refreshDesk()
        if (h.run_in_progress && !run) {
          runCursor.current = 0
          setRunEvents([])
          setRun(await api.run(h.run_in_progress))
        }
      } catch (e) {
        if (!stop) noteFailure(e)
      }
    }
    void check()
    const id = setInterval(check, server === 'up' ? 15000 : 4000)
    return () => { stop = true; clearInterval(id) }
  }, [visible, server, run, refreshDesk, noteFailure])

  // During a run: poll the run's events (cursor) and its status about once a second.
  const active = isRunActive(run)
  const runId = run?.run_id ?? null
  useEffect(() => {
    if (!active || !runId || !visible) return
    let stop = false
    const tick = async () => {
      if (inflight.current) return
      inflight.current = true
      try {
        const page = await api.events({ runId, after: runCursor.current, limit: 500 })
        runCursor.current = page.next_cursor
        if (stop) return
        setRunEvents((prev) => mergeEvents(prev, page.events))
        const last = page.events.filter((e) => e.agent).at(-1)
        if (last?.agent) speak(`${agentTitle(last.agent)}: ${describeEvent(last)}`)
        const r = await api.run(runId)
        if (stop) return
        setRun(r)
        if (!isRunActive(r)) {
          const tail = await api.events({ runId, after: runCursor.current, limit: 500 })
          runCursor.current = tail.next_cursor
          setRunEvents((prev) => mergeEvents(prev, tail.events))
          await refreshDesk()
          speak(r.status === 'finished' ? `Run finished for ticket ${r.ticket_id}.` : `Run ${r.status}: ${r.reason ?? ''}`, true)
        }
        setServer('up')
      } catch (e) {
        noteFailure(e)
      } finally {
        inflight.current = false
      }
    }
    void tick()
    const id = setInterval(tick, FAST_MS)
    return () => { stop = true; clearInterval(id) }
  }, [active, runId, visible, refreshDesk, noteFailure, speak])

  // Otherwise: a slow look at the desk log for anything new.
  useEffect(() => {
    if (active || !visible || server !== 'up') return
    let stop = false
    const tick = async () => {
      try {
        const page = deskCursor.current === null
          ? await api.events({ limit: 20 })
          : await api.events({ after: deskCursor.current, limit: 100 })
        if (stop) return
        const hadCursor = deskCursor.current !== null
        deskCursor.current = page.next_cursor
        setRecent((prev) => mergeEvents(prev, page.events).slice(-30))
        if (hadCursor && page.events.length > 0) await refreshDesk()
      } catch (e) {
        noteFailure(e)
      }
    }
    void tick()
    const id = setInterval(tick, SLOW_MS)
    return () => { stop = true; clearInterval(id) }
  }, [active, visible, server, refreshDesk, noteFailure])

  async function startRun() {
    if (selected === null) return
    setStarting(true)
    setStartError(null)
    setSlipResult(null)
    try {
      const r = await api.startRun(selected)
      runCursor.current = 0
      setRunEvents([])
      setRun({ run_id: r.run_id, ticket_id: r.ticket_id, status: 'queued', history: [], created_at: '', finished_at: null,
        decision: null, reason: null, usage: null })
      speak(`Ticket ${r.ticket_id} handed to the team.`, true)
      await refreshDesk()
    } catch (e) {
      noteFailure(e)
      setStartError(messageOf(e))
    } finally {
      setStarting(false)
    }
  }

  async function approve(a: Approval, name: string) {
    setSlipBusy(true)
    try {
      const r = await api.approve(a.id, name)
      if (r.ok && r.kind === 'payment') setSlipResult({ id: a.id, kind: 'paid', result: r })
      else if (r.ok) setSlipResult({ id: a.id, kind: 'po', note: r.note })
      else setSlipResult({ id: a.id, kind: 'refused', reason: r.reason, status: r.proposal_status, note: r.note })
    } catch (e) {
      noteFailure(e)
      setSlipResult({ id: a.id, kind: 'error', message: messageOf(e) })
    } finally {
      await refreshDesk()
      setSlipBusy(false)
    }
  }

  async function reject(a: Approval, name: string, reason: string) {
    setSlipBusy(true)
    try {
      const r = await api.reject(a.id, name, reason || undefined)
      setSlipResult({ id: a.id, kind: 'rejected', note: r.note })
    } catch (e) {
      noteFailure(e)
      setSlipResult({ id: a.id, kind: 'error', message: messageOf(e) })
    } finally {
      await refreshDesk()
      setSlipBusy(false)
    }
  }

  async function reset() {
    setResetOpen(false)
    try {
      const r = await api.reset()
      setRun(null)
      setRunEvents([])
      setSlipResult(null)
      setStartError(null)
      setResetMsg({ ok: true, text: `Desk cleared. Database restored (checksum ${r.working_sha256.slice(0, 12)}… matches the original); stores emptied; audit trail kept (${r.audit_entries_after} entries).` })
    } catch (e) {
      noteFailure(e)
      setResetMsg({ ok: false, text: messageOf(e) })
    }
    await refreshDesk()
  }

  const view = useMemo(() => deriveDesk(runEvents, run), [runEvents, run])
  const runTicket = run ? tickets.find((t) => t.id === run.ticket_id) ?? null : null
  const isDemo = runEvents.some((e) => e.run_label === 'dashboard-demo')
  const down = server === 'down'

  return (
    <>
      <a className="skip" href="#floor-h">Skip to the floor</a>
      <header className="masthead">
        <div className="brand">
          <svg className="brand__mark" viewBox="0 0 48 48" aria-hidden="true" focusable="false">
            <rect x="8" y="12" width="26" height="30" fill="var(--paper-2)" transform="rotate(-7 21 27)" />
            <rect x="12" y="6" width="26" height="30" fill="var(--paper)" />
            <path d="M17 14 H33 M17 19 H30 M17 24 H27" stroke="var(--navy)" strokeWidth="2.2" />
            <circle cx="34" cy="34" r="8" fill="none" stroke="var(--stamp)" strokeWidth="2.5" />
          </svg>
          <div>
            <h1 className="brand__name">The Back Desk</h1>
            <p className="brand__sub">Campus Customs print shop · where the tickets get worked</p>
          </div>
        </div>
        <p className={`lamp lamp--${server}`}>
          <span className="lamp__bulb" aria-hidden="true" />
          {server === 'up' ? `Desk server on · ${health?.model ?? ''}` : server === 'down' ? 'Desk server unreachable' : 'Checking the desk server…'}
        </p>
      </header>

      {down && (
        <div className="banner" role="alert">
          <strong>Can't reach the desk server at {API_BASE}.</strong> Start it with{' '}
          <code>uvicorn main:app --reload --port 8000</code> from the backend folder. This page retries every few seconds.
        </div>
      )}
      {viewing && (
        <p className="viewing" role="note">
          {viewing.error
            ? `Could not open run ${viewing.runId}: ${viewing.error}`
            : `Viewing finished run ${viewing.runId} read-only, from the desk server's memory. Ticket stamps, approvals, drafts and the till show the desk as it is now.`}
        </p>
      )}
      {isDemo && (
        <p className="demo-flag">Scripted demo playback on scratch data: no model is running; tool results are real scratch data.</p>
      )}

      <main className="desk" aria-busy={active}>
        <div className="col col--left">
          <Tickets tickets={tickets} selected={selected} activeRunTicketId={active ? run?.ticket_id ?? null : null}
            runActive={active || down} startError={startError} starting={starting} onSelect={setSelected} onStart={startRun} />
          <section className="danger-zone" aria-labelledby="reset-h">
            <h2 id="reset-h" className="section-title">End of day <span>reset</span></h2>
            <button type="button" className="btn btn--danger btn--wide" disabled={active || down} onClick={() => setResetOpen(true)}>
              Clear the desk…
            </button>
            {active && <p className="hint">Not while the team is working.</p>}
            {resetMsg && <output className={resetMsg.ok ? 'outcome outcome--ok' : 'outcome outcome--refused'}>{resetMsg.text}</output>}
          </section>
        </div>

        <div className="col col--mid">
          <Floor view={view} run={run} ticketLabel={runTicket ? `ticket ${runTicket.id} · ${runTicket.subject}` : run ? `ticket ${run.ticket_id}` : null} />
          <Decision run={run} />
          <Summaries view={view} />
          <CarbonLog events={run ? runEvents : recent} title={run ? `run ${run.run_id}` : 'recent desk log'} />
        </div>

        <div className="col col--right">
          <Till cash={cash} />
          <Approvals approvals={approvals} busy={slipBusy || down} lastResult={slipResult} onApprove={approve} onReject={reject} />
          <Drafts drafts={drafts} />
        </div>
      </main>

      <footer className="smallprint">
        Every number on this desk comes from the desk server. Money only moves when a person signs a slip.
      </footer>

      <div className="sr-only" aria-live="polite" aria-atomic="true">{announce}</div>

      <Dialog open={resetOpen} onClose={() => setResetOpen(false)} title="Clear the whole desk?" tone="danger">
        <p>This restores the shop database from the original copy and empties the approvals, drafts and resolution notes.
          Payments, resolved tickets and pending signatures will be gone. The audit trail is kept and gets a note.</p>
        <div className="dialog__buttons">
          <button type="button" className="btn btn--ghost" autoFocus onClick={() => setResetOpen(false)}>Keep everything</button>
          <button type="button" className="btn btn--danger" onClick={reset}>Yes, reset the desk</button>
        </div>
      </Dialog>
    </>
  )
}
