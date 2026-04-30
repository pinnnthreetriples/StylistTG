export type SafetySeverity = 'low' | 'medium' | 'high' | 'blocked'
export type HealthStatus = 'ready' | 'attention' | 'blocked' | 'unknown'
export type RiskLevel = 'low' | 'medium' | 'high' | 'blocked' | 'unknown'
export type CapabilityState = 'available' | 'limited' | 'blocked' | 'unknown'

export type AccountSafetyReason = {
  code: string
  severity: SafetySeverity
  source: string
  message: string
  last_seen_at: string | null
}

export type AccountCapability = {
  state: CapabilityState
  reason_codes: string[]
  label: string
  last_checked_at: string | null
  source: string
}

export type AccountRisk = {
  level: RiskLevel
  reasons: AccountSafetyReason[]
}

export type AccountValidityCheck = {
  id: string
  account_id: string
  mode: 'db_snapshot' | 'tdlib_readonly' | 'full_capability' | string
  status: 'running' | 'completed' | 'failed' | 'unsupported' | string
  started_at: string
  finished_at: string | null
  error_code: string | null
  error_class: string | null
  details: Record<string, unknown> | null
  result: Record<string, unknown> | null
  created_at: string
}

export type AccountSafetySummary = {
  account_id: string
  health_status: HealthStatus
  overall_risk_level: RiskLevel
  validity_status: string
  capability_summary: Record<string, CapabilityState>
  top_reasons: AccountSafetyReason[]
  last_checked_at: string
  source: string
}

export type AccountSafety = AccountSafetySummary & {
  capabilities: Record<string, AccountCapability>
  risk_by_operation: Record<string, AccountRisk>
  reasons: AccountSafetyReason[]
  last_validity_check: AccountValidityCheck | null
}

export function healthStatusLabel(status: HealthStatus | string | null | undefined): string {
  return {
    ready: 'Готов',
    attention: 'Требует внимания',
    blocked: 'Заблокирован',
    unknown: 'Неизвестно',
  }[status ?? 'unknown'] ?? 'Неизвестно'
}

export function riskLevelLabel(level: RiskLevel | string | null | undefined): string {
  return {
    low: 'Низкий риск',
    medium: 'Средний риск',
    high: 'Высокий риск',
    blocked: 'Заблокировано',
    unknown: 'Риск неизвестен',
  }[level ?? 'unknown'] ?? 'Риск неизвестен'
}

export function capabilityStateLabel(state: CapabilityState | string | null | undefined): string {
  return {
    available: 'Доступно',
    limited: 'Ограничено',
    blocked: 'Недоступно',
    unknown: 'Неизвестно',
  }[state ?? 'unknown'] ?? 'Неизвестно'
}

export function compactSafetyReasons(safety: Pick<AccountSafetySummary, 'top_reasons'> | null | undefined): string[] {
  return (safety?.top_reasons ?? []).slice(0, 2).map((reason) => reason.message)
}

export function safetyTone(status: HealthStatus | string | null | undefined): 'green' | 'amber' | 'red' | 'gray' {
  if (status === 'ready') return 'green'
  if (status === 'attention') return 'amber'
  if (status === 'blocked') return 'red'
  return 'gray'
}

export function capabilitySummaryLabel(safety: AccountSafety | null | undefined): string {
  if (!safety) return 'Готовность проверяется'
  const profile = capabilityStateLabel(safety.capability_summary.profile_text)
  const music = capabilityStateLabel(safety.capability_summary.profile_music)
  const stories = capabilityStateLabel(safety.capability_summary.story_post)
  return `Профиль: ${profile} · Музыка: ${music} · Истории: ${stories}`
}

export function validityStatusLabel(check: AccountValidityCheck | null | undefined): string {
  if (!check) return 'Проверка ещё не запускалась'
  if (check.status === 'completed') return 'Проверено по данным приложения'
  if (check.status === 'unsupported') return 'Read-only TDLib проверка пока не включена'
  if (check.status === 'failed') return 'Проверка завершилась ошибкой'
  if (check.status === 'running') return 'Проверяем аккаунт'
  return 'Статус проверки неизвестен'
}
