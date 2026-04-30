export type SafetySeverity = 'low' | 'medium' | 'high' | 'blocked'
export type HealthStatus = 'ready' | 'attention' | 'blocked' | 'unknown'
export type RiskLevel = 'low' | 'medium' | 'high' | 'blocked' | 'unknown'
export type CapabilityState = 'available' | 'limited' | 'blocked' | 'unknown'
export type SafetyOperation =
  | 'profile_update'
  | 'username'
  | 'profile_photo'
  | 'profile_music'
  | 'story_post'
  | 'story_delete'
  | 'sync'
  | 'batch_operation'

export type CooldownLevel = 'warning' | 'blocked'

export type AccountOperationCooldown = {
  id: string
  account_id: string
  operation: SafetyOperation | string
  level: CooldownLevel | string
  reason_code: string
  started_at: string
  retry_after_at: string
  source: string
  source_job_id: string | null
  source_step_id: string | null
}

export type UnknownCapabilityPolicy = 'warning_only' | 'block_live_execution'
export type RecentFailurePolicy = 'warning_only' | 'cooldown'
export type FreshValidityPolicy = 'never' | 'if_stale' | 'always_for_live'

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
  cooldown_summary: AccountOperationCooldown[]
  top_reasons: AccountSafetyReason[]
  last_checked_at: string
  source: string
}

export type AccountSafety = AccountSafetySummary & {
  capabilities: Record<string, AccountCapability>
  risk_by_operation: Record<string, AccountRisk>
  cooldowns_by_operation: Record<string, AccountOperationCooldown[]>
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

export function safetyOperationLabel(operation: SafetyOperation | string | null | undefined): string {
  return {
    profile_update: 'Профиль',
    username: 'Username',
    profile_photo: 'Фото',
    profile_music: 'Музыка',
    story_post: 'Истории',
    story_delete: 'Удаление историй',
    sync: 'Синхронизация',
    batch_operation: 'Пакетные действия',
  }[operation ?? ''] ?? 'Операция'
}

export function cooldownLevelLabel(level: CooldownLevel | string | null | undefined): string {
  return level === 'blocked' ? 'Пауза блокирует запуск' : 'Пауза безопасности'
}

export function cooldownSummaryLabel(cooldown: AccountOperationCooldown, now = Date.now()): string {
  const retryAt = Date.parse(cooldown.retry_after_at)
  const operation = safetyOperationLabel(cooldown.operation)
  if (!Number.isFinite(retryAt)) {
    return `${operation}: активная пауза`
  }
  const diffMinutes = Math.max(0, Math.ceil((retryAt - now) / 60000))
  if (diffMinutes <= 0) {
    return `${operation}: пауза завершается`
  }
  if (diffMinutes < 60) {
    return `${operation}: через ${diffMinutes} мин`
  }
  return `${operation}: через ${Math.ceil(diffMinutes / 60)} ч`
}

export function activeCooldownLabels(
  safety: Pick<AccountSafetySummary, 'cooldown_summary'> | null | undefined,
): string[] {
  return (safety?.cooldown_summary ?? []).slice(0, 2).map((cooldown) => cooldownSummaryLabel(cooldown))
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

export function compactSafetyStatusLabel(safety: AccountSafetySummary | null | undefined): string {
  if (!safety) return 'Не проверен'
  if (safety.health_status === 'blocked') return 'Нужен вход'
  if ((safety.cooldown_summary ?? []).length > 0) return 'На паузе'
  if (safety.health_status === 'attention') return 'Есть ограничения'
  return healthStatusLabel(safety.health_status)
}

export function compactSafetyTone(safety: AccountSafetySummary | null | undefined): 'green' | 'amber' | 'red' | 'gray' {
  if (!safety) return 'gray'
  if (safety.health_status === 'blocked') return 'red'
  if ((safety.cooldown_summary ?? []).length > 0) return 'amber'
  return safetyTone(safety.health_status)
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

export function validityAgeLabel(check: AccountValidityCheck | null | undefined, now = Date.now()): string {
  const value = check?.finished_at ?? check?.started_at
  if (!value) return 'Проверка не запускалась'
  const timestamp = Date.parse(value)
  if (!Number.isFinite(timestamp)) return 'Возраст проверки неизвестен'
  const diffMinutes = Math.max(0, Math.round((now - timestamp) / 60000))
  if (diffMinutes < 1) return 'Проверено только что'
  if (diffMinutes < 60) return `Проверено ${diffMinutes} мин назад`
  const diffHours = Math.round(diffMinutes / 60)
  if (diffHours < 24) return `Проверено ${diffHours} ч назад`
  return `Проверено ${Math.round(diffHours / 24)} дн назад`
}
