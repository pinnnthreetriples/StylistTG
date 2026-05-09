export type WarmupStatus =
  | 'draft'
  | 'validating'
  | 'scheduled'
  | 'active'
  | 'paused_risk'
  | 'paused_manual'
  | 'completed'
  | 'failed'

export type WarmupExecutionMode = 'dry_run' | 'shadow' | 'passive' | 'network' | 'advanced'

export type WarmupPresetKind = 'express' | 'standard' | 'hardened' | 'custom'

export type WarmupRiskLevel = 'low' | 'medium' | 'high'

export type ProxyCategory = 'datacenter' | 'residential' | 'mobile' | 'unknown'

export type WarmupCheckSeverity = 'error' | 'warning'

export type WarmupReadiness = {
  workers_enabled: boolean
  dry_run: boolean
  redis_connected: boolean
  database_connected: boolean
  active_sessions: number
  strategies_available: number
}

export type WarmupDailyLimits = {
  feed_read?: number
  join_chat?: number
  p2p_send?: number
  [actionType: string]: number | undefined
}

export type WarmupSessionWindowConfig = {
  micro_sessions_per_day?: { min?: number; max?: number }
  minutes_per_session?: { min?: number; max?: number }
  quiet_hours_local?: { start?: number; end?: number }
}

export type WarmupUiSummary = {
  audience_hint?: string
  speed_hint?: string
  risk_level?: WarmupRiskLevel
}

export type WarmupProxySnapshot = {
  proxy_type: string
  proxy_category: ProxyCategory | string
  host: string
  port: number
  status: string
  last_checked_at: string | null
}

export type WarmupStrategy = {
  id: string
  name: string
  description: string | null
  is_preset: boolean
  preset_kind: WarmupPresetKind
  execution_mode: WarmupExecutionMode
  duration_days: number
  daily_action_limits: Record<string, WarmupDailyLimits>
  session_window_config: WarmupSessionWindowConfig
  ui_summary: WarmupUiSummary
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
  execution_mode: WarmupExecutionMode
  duration_days: number
  current_day: number
  cadence_hours: number
  next_step_at: string | null
  next_micro_session_at: string | null
  updated_at: string
}

export type WarmupDailyCounters = Record<string, WarmupDailyLimits>

export type WarmupSessionDetail = WarmupSessionSummary & {
  strategy_id: string
  timezone: string | null
  last_step_at: string | null
  next_attempt_at: string | null
  last_micro_session_at: string | null
  consecutive_failures: number
  daily_counters: WarmupDailyCounters
  trusted_peer_ids: string[]
  proxy_snapshot: WarmupProxySnapshot | null
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

export type WarmupIsolationClaim = {
  account_id: string
  workspace_id: string
  held_by: string
  reason: string
  acquired_at: string
}

export type WarmupIsolationStatus = {
  is_isolated: boolean
  claim: WarmupIsolationClaim | null
}
