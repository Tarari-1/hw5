// Typed client for the desk server (backend/main.py). Every type below mirrors the
// JSON that route actually returns; field names are kept exactly as the server sends them.

export const API_BASE: string = (import.meta.env.VITE_API_BASE ?? 'http://localhost:8000').replace(/\/+$/, '')

export const AGENT_NAMES = ['boss', 'inventory', 'accounting', 'facilities', 'customer_service'] as const
export type AgentName = (typeof AGENT_NAMES)[number]

// GET /api/tickets
export type TicketStatus = 'open' | 'resolved' | 'declined'
export interface Ticket {
  id: number
  type: string
  requester: string
  subject: string
  status: TicketStatus
  resolution_note: string | null
  pending_approvals: number
  pending_approval_ids: string[]
}

// POST /api/tickets/{id}/run  (HTTP 202)
export interface RunStarted {
  run_id: string
  ticket_id: number
  status: 'queued'
  status_url: string
}

// GET /api/runs/{run_id}  (BossDecision mirrors backend/models.py)
export type RunStatus = 'queued' | 'running' | 'finished' | 'stopped' | 'error'
export interface Finding {
  fact: string
  source_tool: string
}
export interface DecisionAction {
  description: string
  owner: AgentName | 'human'
  state: 'taken' | 'proposed'
  needs_human_approval: boolean
}
export interface BossDecision {
  ticket_id: number | null
  worked_on_by: AgentName[]
  final_decision: string
  findings: Finding[]
  actions: DecisionAction[]
  human_approval_needed: boolean
  approval_items: string[]
  ticket_status_set: 'resolved' | 'declined' | null
}
export interface Run {
  run_id: string
  ticket_id: number
  status: RunStatus
  history: { status: RunStatus; at: string }[]
  created_at: string
  finished_at: string | null
  decision: BossDecision | null
  reason: string | null
  usage: Record<string, number> | null
}

// GET /api/events
export type StepType =
  | 'model_request'
  | 'tool_call'
  | 'tool_result'
  | 'delegation'
  | 'final_answer'
  | 'limit_stop'
  | 'error'
  | 'note'
export interface DeskEvent {
  seq: number
  ts: string
  run_id: string
  run_label: string
  ticket_id: number | null
  agent: AgentName | null
  depth: number | null
  parent_agent: AgentName | null
  step: StepType
  name: string | null
  summary: string | null
  stop_reason: string | null
  // Older audit entries carry "[REDACTED]" strings here, so values may be text.
  usage: Record<string, number | string> | null
}
export interface EventsPage {
  events: DeskEvent[]
  next_cursor: number
  total: number
  limit: number
}

// GET /api/approvals
export type ApprovalStatus = 'pending' | 'approved' | 'rejected' | 'executed'
export interface Approval {
  id: string
  kind: 'payment' | 'purchase_order'
  payment_kind: 'invoice' | 'rent' | null
  status: ApprovalStatus
  amount: number | null
  target: string
  vendor_id: number | null
  ref_id: number | null
  reason: string | null
  expected_arrival: string | null
  created_at: string
  proposed_by: string
  ticket_id: number | null
  approved_by: string | null
  failures: { at: string; attempted_by: string; reason: string }[]
}

// POST /api/approvals/{id}/approve
export interface ApprovedPayment {
  ok: true
  kind: 'payment'
  approved_by: string
  payment: { id: number; kind: string; ref_id: number; amount: number; account: string; paid_at: string; approved_by: string }
  effect: Record<string, string | number>
  cash_before: number
  cash_after: number
  proposal_id: string
}
export interface ApprovedPurchaseOrder {
  ok: true
  kind: 'purchase_order'
  proposal: Record<string, unknown>
  note: string
}
export interface PaymentRefused {
  ok: false
  refused: true
  reason: string
  proposal_status: ApprovalStatus | null
  note: string
  cash: { balance: number | null; as_of: string | null }
}
export type ApproveResult = ApprovedPayment | ApprovedPurchaseOrder | PaymentRefused

// POST /api/approvals/{id}/reject
export interface Rejected {
  ok: true
  proposal: Record<string, unknown>
  note: string
}

// GET /api/cash
export interface Cash {
  account: string
  balance: number
  as_of: string
}

// GET /api/drafts
export interface Draft {
  id: string
  ticket_id: number
  recipient: string
  subject: string
  body: string
  status: 'draft'
  sent: false
  created_at: string
}

// POST /api/reset
export interface ResetResult {
  ok: true
  original_sha256: string
  working_sha256: string
  checksums_match: boolean
  row_counts: Record<string, number>
  stores: Record<string, string>
  audit_entries_before: number
  audit_entries_after: number
  duration_ms: number
}

// GET /api/health
export interface Health {
  ok: true
  model: string
  database: string
  stores: string
  runner: string
  run_in_progress: string | null
  limits: Record<string, number | string>
  cors_origins: string[]
}

// --- transport -----------------------------------------------------------------------

/** The server answered with an error status; `message` is the server's own text. */
export class ApiError extends Error {
  readonly status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

/** The server could not be reached at all (down, wrong URL, or timed out). */
export class ServerUnreachable extends Error {}

interface ValidationIssue {
  loc: (string | number)[]
  msg: string
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

/** Turn FastAPI's {detail: string | issue[]} into one readable sentence. */
export function errorMessage(body: unknown, status: number): string {
  if (isRecord(body)) {
    const detail = body.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      const issues = detail.filter(isRecord) as unknown as ValidationIssue[]
      const text = issues.map((i) => `${String(i.loc.at(-1) ?? 'input')}: ${i.msg}`).join('; ')
      if (text) return text
    }
    if (typeof body.reason === 'string') return body.reason
  }
  return `The desk server answered ${status}.`
}

async function request<T>(path: string, init: RequestInit = {}, timeoutMs = 15000): Promise<{ status: number; body: T }> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  let res: Response
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...init,
      signal: controller.signal,
      headers: init.body ? { 'Content-Type': 'application/json' } : undefined,
    })
  } catch {
    throw new ServerUnreachable(`Can't reach the desk server at ${API_BASE}.`)
  } finally {
    clearTimeout(timer)
  }
  let body: unknown = null
  try {
    body = await res.json()
  } catch {
    body = null
  }
  return { status: res.status, body: body as T }
}

async function getJson<T>(path: string): Promise<T> {
  const { status, body } = await request<unknown>(path)
  if (status >= 400) throw new ApiError(status, errorMessage(body, status))
  return body as T
}

async function postJson<T>(path: string, payload: unknown, timeoutMs?: number): Promise<T> {
  const { status, body } = await request<unknown>(path, { method: 'POST', body: JSON.stringify(payload) }, timeoutMs)
  if (status >= 400) throw new ApiError(status, errorMessage(body, status))
  return body as T
}

// --- routes ----------------------------------------------------------------------------

export const api = {
  health: () => getJson<Health>('/api/health'),
  tickets: async () => (await getJson<{ tickets: Ticket[] }>('/api/tickets')).tickets,
  startRun: (ticketId: number) => postJson<RunStarted>(`/api/tickets/${ticketId}/run`, {}),
  run: (runId: string) => getJson<Run>(`/api/runs/${encodeURIComponent(runId)}`),
  events: (opts: { after?: number; runId?: string; limit?: number }) => {
    const q = new URLSearchParams()
    if (opts.after !== undefined) q.set('after', String(opts.after))
    if (opts.runId) q.set('run_id', opts.runId)
    if (opts.limit !== undefined) q.set('limit', String(opts.limit))
    return getJson<EventsPage>(`/api/events?${q.toString()}`)
  },
  approvals: async (status?: ApprovalStatus) =>
    (await getJson<{ approvals: Approval[] }>(`/api/approvals${status ? `?status=${status}` : ''}`)).approvals,
  /** A refused payment (HTTP 409 with refused: true) is a normal result, not an exception. */
  approve: async (id: string, approvedBy: string): Promise<ApproveResult> => {
    const { status, body } = await request<unknown>(
      `/api/approvals/${encodeURIComponent(id)}/approve`,
      { method: 'POST', body: JSON.stringify({ approved_by: approvedBy }) },
      60000,
    )
    if (status === 409 && isRecord(body) && body.refused === true) return body as unknown as PaymentRefused
    if (status >= 400) throw new ApiError(status, errorMessage(body, status))
    return body as ApproveResult
  },
  reject: (id: string, rejectedBy: string, reason?: string) =>
    postJson<Rejected>(`/api/approvals/${encodeURIComponent(id)}/reject`, {
      rejected_by: rejectedBy,
      ...(reason ? { reason } : {}),
    }),
  cash: () => getJson<Cash>('/api/cash'),
  drafts: async () => (await getJson<{ drafts: Draft[] }>('/api/drafts')).drafts,
  reset: () => postJson<ResetResult>('/api/reset', { confirm: true }, 60000),
}
