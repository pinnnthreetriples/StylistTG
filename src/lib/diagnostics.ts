export type RuntimeDiagnostics = {
  database: string
  redis: string
  tdlib: string
}

export type AccountRuntimeDiagnostics = {
  account_id: string
  account_state: string
  runtime_health: string
  reauth_required: boolean
  authorized_last_confirmed_at: string | null
  can_start_profile_job: boolean
  last_error_code: string | null
  last_error_class: string | null
  tdlib_configured: boolean
  manual_intervention_required?: boolean
  recovery_marker?: string | null
  lock_owner?: string | null
  lock_epoch?: number
  diagnostic_timestamp: string
}

export type DiagnosticItem = {
  key: 'database' | 'redis' | 'tdlib' | 'runtime' | 'last_error' | 'safety' | 'lock'
  label: string
  status: 'ok' | 'down' | 'attention'
  message: string
}

export function buildDiagnosticItems(
  runtime: RuntimeDiagnostics | null,
  account: AccountRuntimeDiagnostics | null,
): DiagnosticItem[] {
  const items: DiagnosticItem[] = []

  if (runtime) {
    items.push(
      buildServiceItem('database', 'Database', runtime.database),
      buildServiceItem('redis', 'Redis', runtime.redis),
      buildServiceItem('tdlib', 'TDLib', runtime.tdlib),
    )
  }

  if (account) {
      items.push({
        key: 'runtime',
        label: 'Runtime',
        status: account.can_start_profile_job && !account.reauth_required ? 'ok' : 'attention',
        message: labelIssue(account.runtime_health),
      })

    if (account.last_error_code) {
      items.push({
        key: 'last_error',
        label: 'Последняя ошибка',
        status: 'attention',
        message: labelIssue(account.last_error_code),
      })
    }
    if (account.manual_intervention_required) {
      items.push({
        key: 'safety',
        label: 'Safety',
        status: 'attention',
        message: 'Нужно ручное вмешательство',
      })
    }
    if (account.lock_owner) {
      items.push({
        key: 'lock',
        label: 'Lock',
        status: 'attention',
        message: `${account.lock_owner} #${account.lock_epoch ?? 0}`,
      })
    }
  }

  return items
}

function buildServiceItem(
  key: 'database' | 'redis' | 'tdlib',
  label: string,
  value: string,
): DiagnosticItem {
  const isOk = value === 'ok' || (key === 'tdlib' && value === 'configured')
  return {
    key,
    label,
    status: isOk ? 'ok' : 'down',
    message: isOk ? (key === 'tdlib' ? 'Настроен' : 'Готова') : 'Недоступен',
  }
}
import { labelIssue } from '@/lib/uiLabels'
