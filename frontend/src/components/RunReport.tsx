import { AGENT_NAMES, type DeskEvent, type Run } from '../api'
import { AGENTS, AgentMark, agentTitle } from '../agents'
import { clock } from '../format'
import { describeEvent, type DeskView } from '../desk'

/** The Boss's memo: copied field by field from the typed BossDecision. */
export function Decision({ run }: { run: Run | null }) {
  if (!run || run.status === 'queued' || run.status === 'running') return null
  if (run.status !== 'finished' || !run.decision) {
    return (
      <section className="memo memo--stopped" aria-labelledby="memo-h">
        <h2 id="memo-h" className="memo__head">Run {run.status}</h2>
        <p>The team did not finish this ticket. Reason from the desk server: <strong>{run.reason ?? 'none given'}</strong></p>
      </section>
    )
  }
  const d = run.decision
  return (
    <section className="memo" aria-labelledby="memo-h">
      <h2 id="memo-h" className="memo__head">
        <span className="memo__from v-boss">Memo from the Boss</span>
        <span className="memo__re">Re: ticket {d.ticket_id ?? run.ticket_id}</span>
      </h2>
      <p className="memo__text">{d.final_decision}</p>
      {d.actions.length > 0 && (
        <ul className="memo__actions">
          {d.actions.map((a, i) => (
            <li key={i}>
              <span className={`chip chip--${a.state}`}>{a.state}</span> {a.description}
              <span className="memo__owner"> · {a.owner === 'human' ? 'a human' : agentTitle(a.owner)}</span>
              {a.needs_human_approval && <span className="memo__sign"> · needs a signature</span>}
            </li>
          ))}
        </ul>
      )}
      <p className={d.human_approval_needed ? 'memo__flag memo__flag--sign' : 'memo__flag'}>
        {d.human_approval_needed
          ? `Human approval needed${d.approval_items.length ? `: ${d.approval_items.join(', ')}` : ''}.`
          : 'No human approval needed.'}
        {d.ticket_status_set && ` Ticket set to ${d.ticket_status_set}.`}
      </p>
    </section>
  )
}

/** Who did what: counts and tools from the events, final words from the API only. */
export function Summaries({ view }: { view: DeskView }) {
  const who = AGENT_NAMES.filter((n) => view.agents[n].tookPart)
  if (who.length === 0) return null
  return (
    <section className="cards" aria-labelledby="cards-h">
      <h2 id="cards-h" className="section-title">Time cards <span>who did what</span></h2>
      <ul className="cards__list">
        {who.map((n) => {
          const a = view.agents[n]
          return (
            <li key={n} className={`card ${AGENTS[n].voice}`}>
              <div className="card__head">
                <AgentMark shape={AGENTS[n].shape} size={24} />
                <span className="card__name">{AGENTS[n].title}</span>
                <span className="card__count">{a.toolCalls} tool{a.toolCalls === 1 ? '' : 's'} · asked {a.delegations}</span>
              </div>
              {a.toolsUsed.length > 0 && (
                <p className="card__tools">{a.toolsUsed.map((t) => <code key={t}>{t}</code>)}</p>
              )}
              {a.finalSummary ? (
                <p className="card__said">
                  “{a.finalSummary}{a.summaryTruncated ? '…' : ''}”
                  {a.summaryTruncated && <span className="quiet"> (shortened in the audit trail)</span>}
                </p>
              ) : (
                <p className="card__said quiet">No final words recorded.</p>
              )}
            </li>
          )
        })}
      </ul>
    </section>
  )
}

/** Carbon copies: every event of the run in order, as plain text. */
export function CarbonLog({ events, title }: { events: DeskEvent[]; title: string }) {
  const rows = [...events].sort((a, b) => b.seq - a.seq).slice(0, 60)
  return (
    <section className="carbon" aria-labelledby="carbon-h">
      <h2 id="carbon-h" className="section-title">Carbon copies <span>{title}</span></h2>
      {rows.length === 0 ? (
        <p className="quiet">Nothing written yet.</p>
      ) : (
        <ol className="carbon__list" reversed>
          {rows.map((e) => (
            <li key={e.seq} className={e.agent ? AGENTS[e.agent].voice : 'v-note'}>
              <span className="carbon__time">{clock(e.ts)}</span>
              <span className="carbon__who">{e.agent ? agentTitle(e.agent) : 'desk'}</span>
              <span className="carbon__what">{describeEvent(e)}</span>
              {e.summary && e.step !== 'final_answer' && <span className="carbon__said">{e.summary}</span>}
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}
