import { AGENT_NAMES, type AgentName, type Run } from '../api'
import { AGENTS, AgentMark, activityLabel, agentTitle } from '../agents'
import type { Delegation, DeskView } from '../desk'

const POS: Record<AgentName, { x: number; y: number }> = {
  boss: { x: 150, y: 26 },
  inventory: { x: 268, y: 106 },
  accounting: { x: 222, y: 228 },
  facilities: { x: 78, y: 228 },
  customer_service: { x: 32, y: 106 },
}

function TeamMap({ delegations }: { delegations: Delegation[] }) {
  const pairs: [AgentName, AgentName][] = []
  AGENT_NAMES.forEach((a, i) => AGENT_NAMES.slice(i + 1).forEach((b) => pairs.push([a, b])))
  const label = delegations.length
    ? `Team map: ${delegations.map((d) => `${d.order}. ${agentTitle(d.from)} asked ${agentTitle(d.to)}`).join('; ')}.`
    : 'Team map: every colleague can ask any other; nobody has asked anyone yet.'
  return (
    // Inline SVG needs role="img" + aria-label; an <img> element cannot hold it.
    // oxlint-disable-next-line jsx-a11y/prefer-tag-over-role
    <svg className="teammap" viewBox="0 0 300 260" role="img" aria-label={label}>
      <defs>
        <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
          <path d="M0 0 L10 5 L0 10 z" fill="var(--ink)" />
        </marker>
      </defs>
      {pairs.map(([a, b]) => (
        <line key={`${a}-${b}`} x1={POS[a].x} y1={POS[a].y} x2={POS[b].x} y2={POS[b].y} className="teammap__line" />
      ))}
      {delegations.map((d) => {
        const p = POS[d.from]
        const q = POS[d.to]
        const len = Math.hypot(q.x - p.x, q.y - p.y)
        const ux = (q.x - p.x) / len
        const uy = (q.y - p.y) / len
        const mx = (p.x + q.x) / 2 - uy * 10
        const my = (p.y + q.y) / 2 + ux * 10
        return (
          <g key={d.order} className={d.refused ? 'teammap__used teammap__used--refused' : 'teammap__used'}>
            <path d={`M${p.x + ux * 20} ${p.y + uy * 20} Q ${mx} ${my} ${q.x - ux * 22} ${q.y - uy * 22}`} markerEnd="url(#arrow)" />
            <circle cx={mx} cy={my} r="8" />
            <text x={mx} y={my + 3.5} textAnchor="middle">{d.order}</text>
          </g>
        )
      })}
      {AGENT_NAMES.map((n) => (
        <g key={n} className={`teammap__node ${AGENTS[n].voice}`} transform={`translate(${POS[n].x - 14} ${POS[n].y - 14})`}>
          <AgentMark shape={AGENTS[n].shape} size={28} />
        </g>
      ))}
    </svg>
  )
}

export function Floor({ view, run, ticketLabel }: { view: DeskView; run: Run | null; ticketLabel: string | null }) {
  return (
    <section className="floor" aria-labelledby="floor-h">
      <h2 id="floor-h" className="section-title">
        The floor <span>{ticketLabel ?? 'nobody is on a ticket'}</span>
      </h2>
      {run && (
        <p className={`runline runline--${run.status}`}>
          <span className="runline__dot" aria-hidden="true" />
          Run {run.run_id} · <strong>{run.status}</strong>
          {run.reason && <> · {run.reason}</>}
        </p>
      )}
      <ul className="plates">
        {AGENT_NAMES.map((n) => {
          const a = view.agents[n]
          const meta = AGENTS[n]
          return (
            <li key={n} className={`plate plate--${meta.shape} ${meta.voice} is-${a.activity.kind}${a.tookPart ? '' : ' is-absent'}`}>
              <AgentMark shape={meta.shape} />
              <div className="plate__who">
                <span className="plate__title">{meta.title}</span>
                <span className="plate__role">{meta.role}</span>
              </div>
              <p className="plate__state">
                <span className="plate__lamp" aria-hidden="true" />
                {activityLabel(a.activity)}
              </p>
              {a.activity.kind === 'stopped' && <p className="plate__reason">{a.activity.reason}</p>}
              {a.tookPart && (
                <p className="plate__tally">
                  {a.toolCalls} tool call{a.toolCalls === 1 ? '' : 's'} · asked {a.delegations}
                </p>
              )}
            </li>
          )
        })}
      </ul>
      <div className="routing">
        <TeamMap delegations={view.delegations} />
        <div className="slip">
          <h3 className="slip__title">Routing slip</h3>
          {view.delegations.length === 0 ? (
            <p className="quiet">No hand-offs yet. Any colleague can ask any other (20 lines open).</p>
          ) : (
            <ol className="slip__list">
              {view.delegations.map((d) => (
                <li key={d.order}>
                  <span className={`who ${AGENTS[d.from].voice}`}>{agentTitle(d.from)}</span>
                  <span aria-hidden="true"> → </span>
                  <span className="sr-only"> asked </span>
                  <span className={`who ${AGENTS[d.to].voice}`}>{agentTitle(d.to)}</span>
                  <span className="slip__status">
                    {d.refused ? `refused: ${d.refused}` : d.answered ? 'answered' : 'waiting for answer'}
                  </span>
                </li>
              ))}
            </ol>
          )}
        </div>
      </div>
    </section>
  )
}
