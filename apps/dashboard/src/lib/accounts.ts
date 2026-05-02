import type { AccountListItem } from '@/lib/api'
import type { AccountSafetySummary } from '@/lib/accountSafety'

export type AccountFilter = 'all' | 'authorized' | 'waiting' | 'error'
export type AccountAdvancedFilter = 'all' | 'safety_ready' | 'needs_login' | 'paused' | 'limited' | 'unchecked'

export type AccountStatusKind = 'authorized' | 'waiting' | 'error'

export type AccountStatus = {
  kind: AccountStatusKind
  label: string
  detail: string
}

const waitingStates = new Set(['registered', 'auth_pending', 'awaiting_code', 'awaiting_password'])
const errorStates = new Set(['runtime_broken', 'reauth_required', 'manual_intervention_needed', 'disabled'])

export function accountStatus(account: AccountListItem): AccountStatus {
  if (account.is_execution_usable || account.account_state === 'authorized_ready') {
    return { kind: 'authorized', label: 'Авторизован', detail: 'Готов к работе' }
  }

  if (errorStates.has(account.account_state) || account.runtime_health === 'timeout') {
    return { kind: 'error', label: 'Ошибка', detail: 'Требуется авторизация' }
  }

  if (waitingStates.has(account.account_state)) {
    return { kind: 'waiting', label: account.account_state === 'awaiting_code' ? 'Ожидает кода' : 'Требует входа', detail: 'Нужно завершить вход' }
  }

  return { kind: 'error', label: 'Проверить', detail: 'Требуется проверка' }
}

export function accountStats(accounts: AccountListItem[]) {
  return accounts.reduce(
    (stats, account) => {
      const status = accountStatus(account)
      stats.total += 1
      stats[status.kind] += 1
      return stats
    },
    { total: 0, authorized: 0, waiting: 0, error: 0 },
  )
}

export function accountMatchesFilter(account: AccountListItem, filter: AccountFilter): boolean {
  return filter === 'all' || accountStatus(account).kind === filter
}

export function accountMatchesAdvancedFilter(
  account: AccountListItem,
  safety: AccountSafetySummary | null | undefined,
  filter: AccountAdvancedFilter,
): boolean {
  if (filter === 'all') return true
  if (!safety) return filter === 'unchecked'
  if (filter === 'paused') return (safety.cooldown_summary ?? []).length > 0
  if (filter === 'needs_login') return safety.health_status === 'blocked'
  if (filter === 'safety_ready') {
    return account.is_execution_usable && safety.health_status === 'ready' && (safety.cooldown_summary ?? []).length === 0
  }
  if (filter === 'limited') {
    return safety.health_status === 'attention' || ['medium', 'high'].includes(safety.overall_risk_level)
  }
  return false
}

export function accountMatchesSearch(account: AccountListItem, query: string): boolean {
  const normalized = query.trim().toLowerCase()
  if (!normalized) return true

  return [
    account.display_name,
    account.username,
    account.phone_number,
    account.telegram_user_id,
  ].some((value) => value?.toLowerCase().includes(normalized))
}

export function maskPhone(phone: string): string {
  const digits = phone.replace(/\D/g, '')
  if (digits.length < 6) return phone

  const prefix = phone.startsWith('+') ? `+${digits.slice(0, 3)}` : digits.slice(0, 3)
  return `${prefix} *** **-${digits.slice(-2)}`
}
