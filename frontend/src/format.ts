import type { Ticket } from './api'

const usd = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' })

/** $3,400.00 — always two decimals; null/undefined become an em dash, never $0. */
export function money(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return usd.format(value)
}

/** Signed change with a true minus sign: −$840.00 / +$12.50. Zero gives $0.00. */
export function moneyDelta(before: number, after: number): string {
  const diff = Math.round((after - before) * 100) / 100
  if (diff === 0) return usd.format(0)
  return `${diff < 0 ? '−' : '+'}${usd.format(Math.abs(diff))}`
}

export type DeskTicketState = 'open' | 'working' | 'waiting' | 'resolved' | 'declined'

/** How a ticket should read on the desk. Pending approvals keep an open ticket "waiting". */
export function ticketState(t: Ticket, activeRunTicketId: number | null): DeskTicketState {
  if (t.status === 'resolved') return 'resolved'
  if (t.status === 'declined') return 'declined'
  if (activeRunTicketId === t.id) return 'working'
  if (t.pending_approvals > 0) return 'waiting'
  return 'open'
}

export function ticketStateLabel(state: DeskTicketState, pending: number): string {
  switch (state) {
    case 'resolved':
      return pending > 0 ? `resolved · ${pending} signature${pending === 1 ? '' : 's'} still needed` : 'resolved'
    case 'declined':
      return 'declined'
    case 'working':
      return 'open · team working'
    case 'waiting':
      return `open, waiting for a human (${pending} to sign)`
    case 'open':
      return 'open'
  }
}

/** customer_order -> Customer order */
export function humanize(snake: string): string {
  const words = snake.replace(/_/g, ' ').trim()
  return words.charAt(0).toUpperCase() + words.slice(1)
}

/** 2026-10-13T19:46:41.123Z -> 19:46:41 (local time). */
export function clock(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleTimeString('en-US', { hour12: false })
}
