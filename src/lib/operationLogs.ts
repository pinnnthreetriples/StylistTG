export type OperationLog = {
  id: string
  account_id: string
  operation_type: string
  operation_key: string | null
  status: string
  severity: string
  source: string
  message: string
  error_code: string | null
  error_class: string | null
  metadata: Record<string, unknown>
  request_id: string | null
  job_id: string | null
  step_id: string | null
  created_at: string
}

export type OperationLogPage = {
  items: OperationLog[]
  total: number
  limit: number
  offset: number
}

export function operationTypeLabel(type: string): string {
  const labels: Record<string, string> = {
    validity_check: 'Проверка аккаунта',
    safety_override: 'Ручной разбор safety',
    account_update: 'Изменение профиля',
    proxy: 'Проверка proxy',
    sync: 'Синхронизация профиля',
    story: 'Истории',
    music: 'Музыка',
  }
  return labels[type] ?? 'Операция'
}

export function operationStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    completed: 'Успешно',
    failed: 'Ошибка',
    partially_completed: 'Частично',
    blocked: 'Заблокировано',
    queued: 'В очереди',
    running: 'Выполняется',
  }
  return labels[status] ?? status
}

export function compactOperationLogLabel(log: OperationLog): string {
  const type = operationTypeLabel(log.operation_type)
  const status = operationStatusLabel(log.status)
  return `${type} — ${status}`
}
