import { describe, expect, it } from 'vitest'
import type { DeskEvent, Run, Ticket } from './api'
import { deriveDesk, extractReportSummary, isRunActive, runIdFromSearch } from './desk'
import { money, moneyDelta, ticketState, ticketStateLabel } from './format'

let seq = 0
function ev(partial: Partial<DeskEvent> & Pick<DeskEvent, 'agent' | 'step'>): DeskEvent {
  seq += 1
  return {
    seq, ts: '2026-10-13T12:00:00Z', run_id: 'r1', run_label: 'dashboard-demo', ticket_id: 101,
    depth: 0, parent_agent: null, name: null, summary: null, stop_reason: null, usage: null, ...partial,
  }
}

function run(status: Run['status'], extra: Partial<Run> = {}): Run {
  return { run_id: 'r1', ticket_id: 101, status, history: [], created_at: '', finished_at: null, decision: null,
    reason: null, usage: null, ...extra }
}

const ticket = (over: Partial<Ticket>): Ticket => ({
  id: 101, type: 'customer_order', requester: 'A', subject: 'S', status: 'open', resolution_note: null,
  pending_approvals: 0, pending_approval_ids: [], ...over,
})

describe('deriveDesk', () => {
  const events: DeskEvent[] = [
    ev({ agent: 'boss', step: 'model_request' }),
    ev({ agent: 'boss', step: 'tool_call', name: 'get_ticket' }),
    ev({ agent: 'boss', step: 'tool_result', name: 'get_ticket', summary: '{"found": true}' }),
    ev({ agent: 'boss', step: 'delegation', name: 'delegate_to_inventory' }),
    ev({ agent: 'inventory', step: 'model_request', depth: 1, parent_agent: 'boss' }),
    ev({ agent: 'inventory', step: 'tool_call', name: 'check_stock', depth: 1 }),
  ]

  it('shows who is doing what mid-run', () => {
    const v = deriveDesk(events, run('running'))
    expect(v.agents.boss.activity).toEqual({ kind: 'asking', target: 'inventory' })
    expect(v.agents.inventory.activity).toEqual({ kind: 'tool', tool: 'check_stock' })
    expect(v.agents.accounting.activity).toEqual({ kind: 'idle' })
    expect(v.agents.accounting.tookPart).toBe(false)
    expect(v.delegations).toHaveLength(1)
    expect(v.delegations[0]).toMatchObject({ order: 1, from: 'boss', to: 'inventory', answered: false })
  })

  it('counts tool calls and delegations and copies report summaries from the API', () => {
    const more = [
      ...events,
      ev({ agent: 'inventory', step: 'tool_result', name: 'check_stock', summary: '{"qty": 0}' }),
      ev({ agent: 'inventory', step: 'final_answer', name: 'SpecialistReport' }),
      ev({ agent: 'boss', step: 'tool_result', name: 'delegate_to_inventory',
        summary: '{"agent": "inventory", "status": "complete", "summary": "Size S qty 0."}' }),
      ev({ agent: 'boss', step: 'final_answer', name: 'BossDecision' }),
    ]
    const decision = { ticket_id: 101, worked_on_by: ['boss' as const, 'inventory' as const],
      final_decision: 'Offer size M.', findings: [], actions: [], human_approval_needed: false, approval_items: [],
      ticket_status_set: null }
    const v = deriveDesk(more, run('finished', { decision }))
    expect(v.agents.boss).toMatchObject({ toolCalls: 1, delegations: 1, toolsUsed: ['get_ticket'],
      finalSummary: 'Offer size M.', activity: { kind: 'done' } })
    expect(v.agents.inventory).toMatchObject({ toolCalls: 1, delegations: 0, toolsUsed: ['check_stock'],
      finalSummary: 'Size S qty 0.', activity: { kind: 'done' } })
    expect(v.delegations[0]?.answered).toBe(true)
  })

  it('marks busy agents stopped with the run reason when the run stops', () => {
    const v = deriveDesk(events, run('stopped', { reason: 'usage limit (request_limit of 40)' }))
    expect(v.agents.inventory.activity).toEqual({ kind: 'stopped', reason: 'usage limit (request_limit of 40)' })
    expect(v.agents.boss.activity.kind).toBe('stopped')
    expect(v.agents.facilities.activity).toEqual({ kind: 'idle' })
  })

  it('records a refused delegation without inventing an answer', () => {
    const v = deriveDesk([ev({ agent: 'facilities', step: 'limit_stop', name: 'delegate_to_boss',
      stop_reason: 'max delegation depth 3 reached' })], run('running'))
    expect(v.delegations[0]).toMatchObject({ from: 'facilities', to: 'boss', refused: 'max delegation depth 3 reached' })
    expect(v.agents.boss.finalSummary).toBeNull()
  })

  it('ignores note entries that have no agent', () => {
    const v = deriveDesk([ev({ agent: null, step: 'note', name: 'stub_runner' })], null)
    expect(Object.values(v.agents).every((a) => !a.tookPart)).toBe(true)
  })
})

describe('extractReportSummary', () => {
  it('reads a complete summary', () => {
    expect(extractReportSummary('{"summary": "All \\"good\\"."}')).toEqual({ text: 'All "good".', truncated: false })
  })
  it('reads a summary cut off by the audit writer and flags it', () => {
    expect(extractReportSummary('{"agent": "x", "summary": "Rent 2400.0 due 2026-09-02 (2 da...'))
      .toEqual({ text: 'Rent 2400.0 due 2026-09-02 (2 da', truncated: true })
  })
  it('returns null when there is no summary', () => {
    expect(extractReportSummary('{"ok": true}')).toBeNull()
    expect(extractReportSummary(null)).toBeNull()
  })
})

describe('money formatting', () => {
  it('formats dollars with cents', () => {
    expect(money(3400)).toBe('$3,400.00')
    expect(money(0)).toBe('$0.00')
    expect(money(null)).toBe('—')
  })
  it('shows a drop with a true minus sign', () => {
    expect(moneyDelta(3400, 2560)).toBe('−$840.00')
    expect(moneyDelta(160, 172.5)).toBe('+$12.50')
    expect(moneyDelta(5, 5)).toBe('$0.00')
  })
})

describe('ticket status', () => {
  it('keeps an open ticket with pending approvals as waiting, not done', () => {
    const t = ticket({ pending_approvals: 1 })
    expect(ticketState(t, null)).toBe('waiting')
    expect(ticketStateLabel('waiting', 1)).toBe('open, waiting for a human (1 to sign)')
  })
  it('reads resolved, declined, working and open', () => {
    expect(ticketState(ticket({ status: 'resolved' }), null)).toBe('resolved')
    expect(ticketState(ticket({ status: 'declined' }), null)).toBe('declined')
    expect(ticketState(ticket({}), 101)).toBe('working')
    expect(ticketState(ticket({}), null)).toBe('open')
    expect(ticketStateLabel('resolved', 1)).toBe('resolved · 1 signature still needed')
  })
  it('knows when a run is active', () => {
    expect(isRunActive(run('queued'))).toBe(true)
    expect(isRunActive(run('running'))).toBe(true)
    expect(isRunActive(run('finished'))).toBe(false)
    expect(isRunActive(null)).toBe(false)
  })
})

describe('?run= URL handling', () => {
  it('reads a valid run id', () => {
    expect(runIdFromSearch('?run=124ecff114e0')).toBe('124ecff114e0')
    expect(runIdFromSearch('?foo=1&run=cd5471ed4a62')).toBe('cd5471ed4a62')
  })
  it('ignores missing, malformed or injected values', () => {
    expect(runIdFromSearch('')).toBeNull()
    expect(runIdFromSearch('?run=')).toBeNull()
    expect(runIdFromSearch('?run=124ECFF114E0')).toBeNull()
    expect(runIdFromSearch('?run=124ecff114e0x')).toBeNull()
    expect(runIdFromSearch('?run=../api/reset')).toBeNull()
    expect(runIdFromSearch('?run=%3Cscript%3E')).toBeNull()
  })
})
