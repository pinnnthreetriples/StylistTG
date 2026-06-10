export type WarmupStatus =
  | 'draft'
  | 'validating'
  | 'scheduled'
  | 'cold_soak'
  | 'active'
  | 'paused_risk'
  | 'paused_manual'
  | 'completed'
  | 'failed'

export type WarmupExecutionMode = 'dry_run' | 'shadow' | 'passive' | 'network' | 'advanced'

export type WarmupPresetKind = 'express' | 'standard' | 'hardened' | 'custom'

export type WarmupActionPreset = 'economic' | 'all' | 'minimal'

export type WarmupActionCategory = 'reading' | 'activity' | 'entertainment' | 'social' | 'groups' | 'profile'

export type WarmupActionMetadata = {
  action_type: string
  category: WarmupActionCategory
  traffic_heavy: boolean
  write_action: boolean
  requires_premium: boolean
}

export type WarmupRiskLevel = 'low' | 'medium' | 'high'

export type ProxyCategory = 'datacenter' | 'residential' | 'mobile' | 'unknown'

export type WarmupCheckSeverity = 'error' | 'warning'

export type WarmupEventSeverity = 'info' | 'success' | 'warning' | 'error' | 'debug'

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

export type WarmupCycleConfig = {
  start_hour: number
  end_hour: number
  days_total: number
  current_cycle: number
  started_at: string | null
  active_hours_total: number | null
}

export type WarmupCyclicCreatePayload = {
  account_ids: string[]
  start_hour: number
  end_hour: number
  days_total: number
  strategy_preset: WarmupPresetKind
}

export type WarmupCyclicCreateResponse = {
  items: WarmupSessionDetail[]
}

export type WarmupTimerStatus = 'running' | 'paused' | 'completed' | 'stopped'

export type WarmupSessionTimer = {
  session_id: string
  started_at: string | null
  total_duration_seconds: number
  elapsed_seconds: number
  status: WarmupTimerStatus
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
  proxy_adaptation: WarmupProxyAdaptation | null
}

export type WarmupProxyAdaptation = {
  proxy_category: string
  applied_preset: 'economic' | 'balanced' | 'full'
  disabled_actions: string[]
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
  cold_soak_until: string | null
  updated_at: string
  cycle_config: WarmupCycleConfig | null
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
  disabled_actions: string[]
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
  severity?: WarmupEventSeverity
  payload: Record<string, unknown>
  created_at: string
}

export type WarmupEventPage = {
  items: WarmupEvent[]
  total: number
  page: number
  limit: number
}

export type WarmupLiveEvent = {
  id: string
  event_id: string
  session_id: string
  account_id: string
  account_label: string
  phone_id: string
  event_type: string
  severity: WarmupEventSeverity
  message: string
  payload: Record<string, unknown>
  occurred_at: string
  created_at: string
}

export type WarmupLiveEventAccount = {
  account_id: string
  account_label: string
  phone_id: string
}

export type WarmupLiveEventPage = {
  items: WarmupLiveEvent[]
  total: number
  limit: number
  next_cursor: string | null
  accounts: WarmupLiveEventAccount[]
}

export type WarmupLiveEventFilters = {
  accountId?: string
  severity?: WarmupEventSeverity | 'all'
  cursor?: string | null
  limit?: number
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

export type WarmupSelectableAccount = {
  account_id: string
  display_name: string | null
  username: string | null
  phone_number: string
  role: string
  country: string
  country_iso: string
  validity_badge: 'valid' | 'needs_login' | 'blocked' | 'unknown'
  proxy_badge: 'ok' | 'issue' | 'missing' | 'unknown'
  phase_badge: 'new' | 'warming' | 'in_work'
  tags: string[]
  is_in_work: boolean
}

export type WarmupSelectableAccountFilters = {
  search?: string
  country?: string
  role?: string
  proxyOkOnly?: boolean
  hideInWork?: boolean
}
