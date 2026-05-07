export type WarmupStatus =
  | 'draft'
  | 'validating'
  | 'scheduled'
  | 'active'
  | 'paused_risk'
  | 'paused_manual'
  | 'completed'
  | 'failed'

export type WarmupCheckSeverity = 'error' | 'warning'

export type WarmupReadiness = {
  workers_enabled: boolean
  dry_run: boolean
  redis_connected: boolean
  database_connected: boolean
  active_sessions: number
  strategies_available: number
}

export type WarmupStrategy = {
  id: string
  name: string
  description: string | null
  is_preset: boolean
}

export type WarmupCheckItem = {
  key: string
  label: string
  passed: boolean
  severity: WarmupCheckSeverity
  detail: string | null
}

export type WarmupValidateResponse = {
  is_ready: boolean
  checks: WarmupCheckItem[]
  blocking_reasons: string[]
  warnings: string[]
}

export type WarmupSessionSummary = {
  id: string
  account_id: string
  account_label: string | null
  strategy_name: string
  status: WarmupStatus
  current_day: number
  cadence_hours: number
  next_step_at: string | null
  updated_at: string
}

export type WarmupSessionDetail = WarmupSessionSummary & {
  strategy_id: string
  last_step_at: string | null
  next_attempt_at: string | null
  consecutive_failures: number
  created_at: string
  started_at: string | null
  paused_at: string | null
  completed_at: string | null
  worker_id: string | null
}

export type WarmupSessionPage = {
  items: WarmupSessionSummary[]
  total: number
  page: number
  limit: number
}

export type WarmupEvent = {
  id: string
  event_type: string
  payload: Record<string, unknown>
  created_at: string
}

export type WarmupEventPage = {
  items: WarmupEvent[]
  total: number
  page: number
  limit: number
}
