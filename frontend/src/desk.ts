// Pure functions that turn API data (events + run status) into what the desk shows.
// Nothing here invents text: every sentence shown about an agent is either a fixed
// state label or text copied from an event summary / the Boss's typed decision.
import { AGENT_NAMES, type AgentName, type DeskEvent, type Run } from './api'

export type AgentActivity =
  | { kind: 'idle' }
  | { kind: 'thinking' }
  | { kind: 'tool'; tool: string }
  | { kind: 'asking'; target: AgentName }
  | { kind: 'done' }
  | { kind: 'stopped'; reason: string }

export interface AgentView {
  name: AgentName
  activity: AgentActivity
  tookPart: boolean
  toolCalls: number
  delegations: number
  toolsUsed: string[]
  /** Final words, copied from the API: the Boss's final_decision or the report summary
   *  the specialist returned to whoever asked it. Null if the API has none. */
  finalSummary: string | null
  summaryTruncated: boolean
  lastResult: string | null
}

export interface Delegation {
  order: number
  seq: number
  from: AgentName
  to: AgentName
  depth: number
  answered: boolean
  refused: string | null
}

export interface DeskView {
  agents: Record<AgentName, AgentView>
  delegations: Delegation[]
}

const DELEGATE_PREFIX = 'delegate_to_'

function isAgentName(value: string): value is AgentName {
  return (AGENT_NAMES as readonly string[]).includes(value)
}

export function delegateTarget(toolName: string | null): AgentName | null {
  if (!toolName?.startsWith(DELEGATE_PREFIX)) return null
  const target = toolName.slice(DELEGATE_PREFIX.length)
  return isAgentName(target) ? target : null
}

/** Pull the "summary" field out of an audit result summary (JSON, maybe cut at 240 chars). */
export function extractReportSummary(resultSummary: string | null): { text: string; truncated: boolean } | null {
  if (!resultSummary) return null
  try {
    const parsed: unknown = JSON.parse(resultSummary)
    if (typeof parsed === 'object' && parsed !== null && 'summary' in parsed) {
      const s = (parsed as { summary: unknown }).summary
      if (typeof s === 'string') return { text: s, truncated: false }
    }
  } catch {
    // The audit writer shortens long summaries, which can leave the JSON unterminated.
  }
  const m = /"summary":\s*"((?:[^"\\]|\\.)*)("?)/.exec(resultSummary)
  if (!m || m[1] === undefined) return null
  const raw = m[1].replace(/\.\.\.$/, '')
  let text: string
  try {
    text = JSON.parse(`"${raw.replace(/\\$/, '')}"`) as string
  } catch {
    text = raw
  }
  return { text, truncated: m[2] !== '"' }
}

function blank(name: AgentName): AgentView {
  return {
    name,
    activity: { kind: 'idle' },
    tookPart: false,
    toolCalls: 0,
    delegations: 0,
    toolsUsed: [],
    finalSummary: null,
    summaryTruncated: false,
    lastResult: null,
  }
}

/** Derive every agent's state and summary from one run's events (in seq order) and its status. */
export function deriveDesk(events: DeskEvent[], run: Run | null): DeskView {
  const agents = Object.fromEntries(AGENT_NAMES.map((n) => [n, blank(n)])) as Record<AgentName, AgentView>
  const delegations: Delegation[] = []
  const sorted = [...events].sort((a, b) => a.seq - b.seq)

  for (const e of sorted) {
    if (!e.agent) continue
    const a = agents[e.agent]
    a.tookPart = true
    const target = delegateTarget(e.name)
    switch (e.step) {
      case 'model_request':
        if (a.activity.kind !== 'done') a.activity = { kind: 'thinking' }
        break
      case 'tool_call':
        if (e.name && !target) {
          a.toolCalls += 1
          if (!a.toolsUsed.includes(e.name)) a.toolsUsed.push(e.name)
          a.activity = { kind: 'tool', tool: e.name }
        }
        break
      case 'delegation':
        if (target) {
          a.delegations += 1
          a.activity = { kind: 'asking', target }
          delegations.push({ order: delegations.length + 1, seq: e.seq, from: e.agent, to: target, depth: e.depth ?? 0,
            answered: false, refused: null })
        }
        break
      case 'tool_result':
        if (target) {
          const open = [...delegations].reverse().find((d) => d.from === e.agent && d.to === target && !d.answered)
          if (open) open.answered = true
          const report = extractReportSummary(e.summary)
          if (report && agents[target].finalSummary === null) {
            agents[target].finalSummary = report.text
            agents[target].summaryTruncated = report.truncated
          }
        } else {
          a.lastResult = e.summary
        }
        a.activity = { kind: 'thinking' }
        break
      case 'final_answer':
        a.activity = { kind: 'done' }
        break
      case 'limit_stop':
        if (target) {
          delegations.push({ order: delegations.length + 1, seq: e.seq, from: e.agent, to: target, depth: e.depth ?? 0,
            answered: false, refused: e.stop_reason ?? 'refused' })
        } else if (!e.name) {
          a.activity = { kind: 'stopped', reason: e.stop_reason ?? 'stopped by a limit' }
        }
        break
      case 'error':
        a.activity = { kind: 'stopped', reason: e.stop_reason ?? 'error' }
        break
      case 'note':
        break
    }
  }

  if (run) {
    const ended = run.status === 'finished' || run.status === 'stopped' || run.status === 'error'
    if (ended) {
      for (const a of Object.values(agents)) {
        const busy = a.activity.kind === 'thinking' || a.activity.kind === 'tool' || a.activity.kind === 'asking'
        if (!busy) continue
        a.activity = run.status === 'finished' ? { kind: 'done' } : { kind: 'stopped', reason: run.reason ?? run.status }
      }
    }
    if (run.decision) {
      agents.boss.finalSummary = run.decision.final_decision
      agents.boss.summaryTruncated = false
    }
  }
  return { agents, delegations }
}

/** One fixed-vocabulary line per event for the carbon-copy log (no invented prose). */
export function describeEvent(e: DeskEvent): string {
  const target = delegateTarget(e.name)
  switch (e.step) {
    case 'model_request':
      return 'thinking'
    case 'tool_call':
      return target ? `asks ${target}` : `calls ${e.name ?? 'a tool'}`
    case 'tool_result':
      return target ? `hears back from ${target}` : `${e.name ?? 'tool'} returned`
    case 'delegation':
      return target ? `asks ${target}` : 'delegates'
    case 'final_answer':
      return 'hands in final answer'
    case 'limit_stop':
      return `stopped: ${e.stop_reason ?? 'limit'}`
    case 'error':
      return `error: ${e.stop_reason ?? 'unknown'}`
    case 'note':
      return e.name ?? 'note'
  }
}

export function isRunActive(run: Run | null): boolean {
  return run !== null && (run.status === 'queued' || run.status === 'running')
}

/** ?run=<run_id> opens a finished run read-only. Only the server's 12-hex-digit run ids are accepted. */
export function runIdFromSearch(search: string): string | null {
  const value = new URLSearchParams(search).get('run')
  return value && /^[a-f0-9]{12}$/.test(value) ? value : null
}
