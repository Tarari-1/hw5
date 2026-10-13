import type { Ticket } from '../api'
import { humanize, ticketState, ticketStateLabel } from '../format'

interface Props {
  tickets: Ticket[]
  selected: number | null
  activeRunTicketId: number | null
  runActive: boolean
  startError: string | null
  starting: boolean
  onSelect: (id: number) => void
  onStart: () => void
}

/** The ticket spike: paper tickets clipped to the rail, with stamps for their state. */
export function Tickets({ tickets, selected, activeRunTicketId, runActive, startError, starting, onSelect, onStart }: Props) {
  const chosen = tickets.find((t) => t.id === selected) ?? null
  const blocked = !chosen ? 'Pick a ticket first.' : runActive ? 'The team is already working a ticket.'
    : chosen.status !== 'open' ? `Ticket ${chosen.id} is ${chosen.status}; only open tickets can be worked.` : null

  return (
    <section className="rail" aria-labelledby="rail-h">
      <h2 id="rail-h" className="section-title">The spike <span>open tickets</span></h2>
      {tickets.length === 0 && <p className="quiet">No tickets on the spike yet.</p>}
      <ul className="spike">
        {tickets.map((t) => {
          const state = ticketState(t, activeRunTicketId)
          const label = ticketStateLabel(state, t.pending_approvals)
          return (
            <li key={t.id}>
              <button
                type="button"
                className={`ticket ticket--${state}`}
                aria-pressed={selected === t.id}
                onClick={() => onSelect(t.id)}
              >
                <span className="ticket__clip" aria-hidden="true" />
                <span className="ticket__no">No. {t.id}</span>
                <span className="ticket__type">{humanize(t.type)}</span>
                <span className="ticket__subject">{t.subject}</span>
                <span className="ticket__from">from {t.requester}</span>
                <span className="ticket__state">{label}</span>
                {state === 'resolved' && <span className="stamp stamp--resolved" aria-hidden="true">Resolved</span>}
                {state === 'declined' && <span className="stamp stamp--declined" aria-hidden="true">Declined</span>}
                {state === 'waiting' && <span className="tag-waiting" aria-hidden="true">Needs a signature</span>}
                {t.resolution_note && <span className="ticket__note">Note: {t.resolution_note}</span>}
              </button>
            </li>
          )
        })}
      </ul>
      <div className="start">
        <button type="button" className="btn btn--primary btn--wide" disabled={blocked !== null || starting} onClick={onStart}
          aria-describedby="start-help">
          {starting ? 'Handing it to the Boss…' : chosen ? `Hand ticket ${chosen.id} to the team` : 'Hand a ticket to the team'}
        </button>
        <p id="start-help" className="hint">{blocked ?? 'The Boss reads it first and calls in whoever is needed.'}</p>
        {startError && <p className="refusal" role="alert">The desk server said: {startError}</p>}
      </div>
    </section>
  )
}
