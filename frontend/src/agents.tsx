import type { AgentName } from './api'
import type { AgentActivity } from './desk'

export interface AgentMeta {
  name: AgentName
  title: string
  role: string
  initials: string
  /** css class carrying the agent's typographic voice and ink colour */
  voice: string
  shape: 'seal' | 'crate' | 'ledger' | 'keytag' | 'note'
}

export const AGENTS: Record<AgentName, AgentMeta> = {
  boss: { name: 'boss', title: 'The Boss', role: 'Reads the ticket, decides, signs off', initials: 'BO', voice: 'v-boss', shape: 'seal' },
  inventory: { name: 'inventory', title: 'Inventory', role: 'Stockroom, sizes & restock', initials: 'IN', voice: 'v-inventory', shape: 'crate' },
  accounting: { name: 'accounting', title: 'Accounting', role: 'Cash, bills & margins', initials: 'AC', voice: 'v-accounting', shape: 'ledger' },
  facilities: { name: 'facilities', title: 'Facilities', role: 'The shop space & the rent', initials: 'FA', voice: 'v-facilities', shape: 'keytag' },
  customer_service: { name: 'customer_service', title: 'Customer Service', role: 'Drafts replies (never sends)', initials: 'CS', voice: 'v-cs', shape: 'note' },
}

export function agentTitle(name: string): string {
  return name in AGENTS ? AGENTS[name as AgentName].title : name
}

/** Fixed state vocabulary shown on each nameplate. */
export function activityLabel(a: AgentActivity): string {
  switch (a.kind) {
    case 'idle':
      return 'At the desk'
    case 'thinking':
      return 'Thinking'
    case 'tool':
      return `Using ${a.tool}`
    case 'asking':
      return `Asking ${agentTitle(a.target)}`
    case 'done':
      return 'Done'
    case 'stopped':
      return 'Stopped'
  }
}

/** Original abstract marks: one distinct silhouette per colleague. */
export function AgentMark({ shape, size = 34 }: { shape: AgentMeta['shape']; size?: number }) {
  const common = { width: size, height: size, viewBox: '0 0 40 40', 'aria-hidden': true, focusable: false } as const
  switch (shape) {
    case 'seal':
      return (
        <svg {...common} className="mark">
          <circle cx="20" cy="20" r="17" fill="currentColor" />
          <circle cx="20" cy="20" r="12.5" fill="none" stroke="var(--paper)" strokeWidth="1.6" strokeDasharray="2 2.2" />
          <path d="M20 12 L22.6 18 L29 18.4 L24 22.4 L25.7 28.6 L20 25.1 L14.3 28.6 L16 22.4 L11 18.4 L17.4 18 Z" fill="var(--paper)" />
        </svg>
      )
    case 'crate':
      return (
        <svg {...common} className="mark">
          <rect x="4" y="6" width="32" height="28" fill="currentColor" />
          <rect x="7" y="9" width="26" height="22" fill="none" stroke="var(--paper)" strokeWidth="1.6" />
          <path d="M7 9 L33 31 M7 20 H33" stroke="var(--paper)" strokeWidth="1.6" />
        </svg>
      )
    case 'ledger':
      return (
        <svg {...common} className="mark">
          <rect x="6" y="3" width="28" height="34" rx="1.5" fill="currentColor" />
          <path d="M14 3 V37 M27 3 V37" stroke="var(--paper)" strokeWidth="1.4" />
          <path d="M9 12 H31 M9 18 H31 M9 24 H31 M9 30 H31" stroke="var(--paper)" strokeWidth="1" opacity="0.8" />
        </svg>
      )
    case 'keytag':
      return (
        <svg {...common} className="mark">
          <path d="M20 3 L35 15 V37 H5 V15 Z" fill="currentColor" />
          <circle cx="20" cy="15" r="3.6" fill="var(--paper)" />
          <path d="M11 25 H29 M11 30 H24" stroke="var(--paper)" strokeWidth="1.8" />
        </svg>
      )
    case 'note':
      return (
        <svg {...common} className="mark">
          <path d="M5 6 H35 V27 H18 L10 35 V27 H5 Z" fill="currentColor" />
          <path d="M10 13 H30 M10 19 H25" stroke="var(--paper)" strokeWidth="1.8" />
        </svg>
      )
  }
}
