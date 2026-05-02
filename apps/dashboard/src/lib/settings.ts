export type LivePreflight = {
  tdjson_present: boolean
  tdlib_credentials_present: boolean
  postgres_reachable: boolean
  redis_reachable: boolean
  storage_writable: boolean
  rq_worker_expected: boolean
  rq_worker_status?: 'ready' | 'missing' | 'unknown' | null
  profile_worker_status?: 'ready' | 'missing' | 'unknown' | null
  auth_worker_status?: 'ready' | 'missing' | 'unknown' | null
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
    workerItem('profile_worker', 'Profile worker', preflight, preflight.profile_worker_status ?? preflight.rq_worker_status, 'profile_jobs'),
    workerItem('auth_worker', 'Auth worker', preflight, preflight.auth_worker_status ?? preflight.rq_worker_status, 'auth_jobs'),
    {
      key: 'overall',
      label: 'Live статус',
      status: preflight.overall_status === 'ok' ? 'ok' : 'attention',
      message: formatLiveStatus(preflight.overall_status),
      help: 'Общий итог live-проверок. Готов означает, что приложение может выполнять реальные операции.',
    },
  ]
}

function workerItem(
  key: string,
  label: string,
  preflight: LivePreflight,
  workerStatus: LivePreflight['rq_worker_status'],
  queueName: 'profile_jobs' | 'auth_jobs',
): SettingsStatusItem {
  if (!preflight.rq_worker_expected) {
    return {
      key,
      label,
      status: 'ok',
      message: 'Worker не требуется',
      help: 'Для текущего режима отдельный worker не требуется.',
    }
  }

  if (workerStatus === 'ready') {
    return {
      key,
      label,
      status: 'ok',
      message: 'Готов',
      help: `Worker подтверждён в Redis и может брать задачи из очереди ${queueName}.`,
    }
  }

  const startCommand =
    `Запуск: cd backend; python -m rq.cli worker ${queueName} --url redis://127.0.0.1:6379/0 --worker-class rq.SimpleWorker`

  if (workerStatus === 'missing') {
    return {
      key,
      label,
      status: 'down',
      message: 'Worker не запущен',
      help: `Задачи будут создаваться, но не выполнятся, пока worker не запущен. ${startCommand}`,
    }
  }

  return {
    key,
    label,
    status: 'attention',
    message: 'Worker нужен для выполнения задач',
    help: `Worker не запущен или не подтверждён. Задачи будут создаваться, но могут не выполняться. ${startCommand}`,
  }
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
