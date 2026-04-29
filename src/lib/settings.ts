export type LivePreflight = {
  tdjson_present: boolean
  tdlib_credentials_present: boolean
  postgres_reachable: boolean
  redis_reachable: boolean
  storage_writable: boolean
  rq_worker_expected: boolean
  overall_status: string
}

export type SettingsStatusItem = {
  key: string
  label: string
  status: 'ok' | 'down' | 'attention'
  message: string
  help?: string
}

export function formatCooldown(seconds: number): string {
  if (seconds <= 0) return 'Выключено'
  if (seconds < 60) return `${seconds} сек`
  return `${Math.round(seconds / 60)} мин`
}

export function buildPreflightItems(preflight: LivePreflight | null): SettingsStatusItem[] {
  if (!preflight) return []
  return [
    boolItem('tdjson', 'tdjson.dll', preflight.tdjson_present, 'Файл TDLib, через который приложение общается с Telegram. Если его нет, live-операции не запустятся.'),
    boolItem('tdlib_credentials', 'TDLib API', preflight.tdlib_credentials_present, 'API ID и API Hash Telegram. Нужны TDLib, чтобы авторизовать аккаунты и выполнять действия.'),
    boolItem('postgres', 'PostgreSQL', preflight.postgres_reachable, 'Основная база данных проекта. Здесь хранятся аккаунты, профили, задачи и их статусы.'),
    boolItem('redis', 'Redis', preflight.redis_reachable, 'Быстрое хранилище очереди. Через него backend передает задачи RQ worker.'),
    boolItem('storage', 'Storage', preflight.storage_writable, 'Локальные папки для файлов TDLib и загруженных данных. Проверка показывает, можно ли туда писать.'),
    {
      key: 'worker',
      label: 'RQ worker',
      status: preflight.rq_worker_expected ? 'ok' : 'attention',
      message: preflight.rq_worker_expected ? 'Требуется' : 'Не требуется',
      help: 'Отдельный процесс, который берет задачи из Redis и выполняет изменения профиля через TDLib.',
    },
    {
      key: 'overall',
      label: 'Live статус',
      status: preflight.overall_status === 'ok' ? 'ok' : 'attention',
      message: formatLiveStatus(preflight.overall_status),
      help: 'Общий итог live-проверок. Готов означает, что приложение может выполнять реальные операции.',
    },
  ]
}

function formatLiveStatus(status: string): string {
  if (status === 'ok') return 'Готов'
  if (status === 'degraded') return 'Ограничен'
  return status
}

function boolItem(key: string, label: string, value: boolean, help?: string): SettingsStatusItem {
  return {
    key,
    label,
    status: value ? 'ok' : 'down',
    message: value ? 'Готов' : 'Недоступен',
    help,
  }
}
