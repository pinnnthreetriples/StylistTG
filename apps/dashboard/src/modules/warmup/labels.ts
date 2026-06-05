import type {
  WarmupEvent,
  WarmupEventSeverity,
  WarmupExecutionMode,
  WarmupPresetKind,
  WarmupRiskLevel,
  WarmupStatus,
} from './types'

export const WARMUP_STATUS_LABELS: Record<WarmupStatus, string> = {
  draft: 'Черновик',
  validating: 'Проверка',
  scheduled: 'Запланирована',
  cold_soak: 'Cold soak',
  active: 'Идёт подготовка',
  paused_risk: 'Пауза по риску',
  paused_manual: 'Пауза',
  completed: 'Завершена',
  failed: 'Ошибка',
}

export const WARMUP_PRESET_LABELS: Record<WarmupPresetKind, string> = {
  express: 'Экспресс',
  standard: 'Стандарт',
  hardened: 'Усиленный',
  custom: 'Кастомный',
}

export const WARMUP_EXECUTION_MODE_LABELS: Record<WarmupExecutionMode, string> = {
  dry_run: 'Безопасный режим',
  shadow: 'Теневая симуляция',
  passive: 'Только чтение',
  network: 'Осторожный сетевой режим',
  advanced: 'Расширенный (экспериментальный)',
}

export const WARMUP_RISK_LEVEL_LABELS: Record<WarmupRiskLevel, string> = {
  low: 'Низкий риск',
  medium: 'Средний риск',
  high: 'Повышенный риск',
}

export const WARMUP_RISK_TONES: Record<WarmupRiskLevel, 'green' | 'amber' | 'red'> = {
  low: 'green',
  medium: 'amber',
  high: 'red',
}

export const WARMUP_EVENT_SEVERITY_LABELS: Record<WarmupEventSeverity | 'all', string> = {
  all: 'Все',
  info: 'Инфо',
  success: 'Успех',
  warning: 'Предупреждение',
  error: 'Ошибка',
  debug: 'Дебаг',
}

export const WARMUP_EVENT_LABELS: Record<string, string> = {
  session_created: 'Сессия создана',
  task_executed: 'Шаг выполнен',
  task_skipped: 'Шаг пропущен',
  task_failed: 'Шаг завершился ошибкой',
  day_advanced: 'День обновлён',
  completed: 'Подготовка завершена',
  paused: 'Пауза включена',
  resumed: 'Подготовка возобновлена',
  disabled_actions_updated: 'Отключённые действия обновлены',
  proxy_adaptation_applied: 'Proxy preset применён',
  queue_enqueue_failed: 'Очередь недоступна',
  // Backend now emits 'triggered'; 'tripped' kept for events already in DB
  circuit_breaker_triggered: 'Защита остановила сессию',
  circuit_breaker_tripped: 'Защита остановила сессию',
  session_action_executed: 'Действие выполнено',
  session_action_simulated: 'Симуляция действия',
  micro_session_window_opened: 'Окно микро-сессии открыто',
  micro_session_window_closed: 'Окно микро-сессии закрыто',
  p2p_contact_recorded: 'P2P-контакт зафиксирован',
  p2p_contact_recording_failed: 'Ошибка записи P2P-контакта',
  isolation_claimed: 'Аккаунт изолирован прогревом',
  isolation_released: 'Изоляция снята',
  cold_soak_started: 'Началась фаза тишины',
  cold_soak_in_progress: 'Фаза тишины продолжается',
  cold_soak_completed: 'Фаза тишины завершена',
}

/** Human-readable labels for task_skipped reason codes emitted by dispatch. */
export const WARMUP_SKIP_REASON_LABELS: Record<string, string> = {
  quiet_hours: 'Тихие часы — действия не выполняются',
  passive_disabled: 'Live-адаптер недоступен',
  disabled_by_operator: 'Отключено оператором для этой сессии',
  write_action_not_enabled: 'Запись не разрешена текущим режимом',
  no_target_channels_configured: 'Нет целевых каналов в стратегии',
  no_browse_target_available: 'Нет канала для чтения',
  not_subscribed: 'Аккаунт ещё не подписан на канал',
  no_scroll_channel_available: 'Нет подписанного канала для прокрутки',
  no_open_poll_found: 'В подписанных каналах нет открытого опроса',
  no_video_found: 'В подписанных каналах нет подходящего видео',
  no_voice_found: 'В подписанных каналах нет voice/audio сообщения',
  no_forward_source_available: 'Нет сообщения для безопасной пересылки',
  no_contacts_pool_available: 'Нет пула контактов для синхронизации',
  protected_chat: 'Служебный или защищённый чат пропущен',
  no_chat_target_available: 'Нет подходящего чата для действия',
  non_premium_account: 'Действие доступно только Premium-аккаунту',
  no_stories_in_channel: 'В канале нет активных сторис',
  no_reactions_in_channel: 'Для канала нет доступных реакций',
  safety_gate_blocked: 'Safety gate заблокировал действие',
  no_eligible_trusted_peers: 'Нет доступных доверенных партнёров',
  text_provider_unavailable: 'Провайдер текста недоступен',
  text_provider_empty_render: 'Провайдер текста вернул пустой результат',
}

export function formatWarmupEventPayload(event: WarmupEvent): string {
  const day = event.payload.day !== undefined ? String(event.payload.day) : '-'
  if (event.event_type === 'session_created') {
    const mode = String(event.payload.execution_mode ?? 'dry_run')
    return `Сессия поставлена в расписание. Режим: ${mode}.`
  }
  if (event.event_type === 'cold_soak_started') {
    const until = event.payload.until ? formatWarmupDate(String(event.payload.until)) : 'позже'
    return `Аккаунт остаётся без действий до ${until}.`
  }
  if (event.event_type === 'cold_soak_in_progress') {
    const until = event.payload.until ? formatWarmupDate(String(event.payload.until)) : 'позже'
    return `Фаза тишины ещё идёт. Старт после ${until}.`
  }
  if (event.event_type === 'cold_soak_completed') return 'Фаза тишины завершена, сессия возвращена в расписание.'
  if (event.event_type === 'task_executed') return `Dry-run шаг записан: день ${day}.`
  if (event.event_type === 'day_advanced') return `Следующий день подготовки: ${day}.`
  if (event.event_type === 'paused') return `Причина: ${String(event.payload.reason ?? 'ручная пауза')}.`
  if (event.event_type === 'resumed') return 'Сессия вернулась в расписание.'
  if (event.event_type === 'disabled_actions_updated') {
    const disabled = Array.isArray(event.payload.disabled_actions)
      ? event.payload.disabled_actions.map(String).join(', ')
      : ''
    return disabled ? `Отключены действия: ${disabled}.` : 'Все действия снова включены.'
  }
  if (event.event_type === 'proxy_adaptation_applied') {
    const preset = String(event.payload.applied_preset ?? 'balanced')
    const category = String(event.payload.proxy_category ?? 'unknown')
    const disabled = Array.isArray(event.payload.disabled_actions)
      ? event.payload.disabled_actions.map(String).join(', ')
      : ''
    return disabled
      ? `Preset ${preset} применён для proxy ${category}. Отключены: ${disabled}.`
      : `Preset ${preset} применён для proxy ${category}.`
  }
  if (event.event_type === 'completed') return 'План подготовки завершён.'
  if (event.event_type === 'queue_enqueue_failed') return 'Сессия остановлена, потому что задача не попала в RQ.'
  if (event.event_type === 'task_skipped') {
    const rawReason = String(event.payload.reason ?? '')
    const reasonLabel = WARMUP_SKIP_REASON_LABELS[rawReason] ?? rawReason
    const action = event.payload.action_type ? ` (${String(event.payload.action_type)})` : ''
    return `Шаг${action} пропущен: ${reasonLabel}.`
  }
  if (event.event_type === 'task_failed') {
    const action = event.payload.action_type ? String(event.payload.action_type) : 'действие'
    const errorCode = event.payload.error_code ? ` [${String(event.payload.error_code)}]` : ''
    return `Ошибка при выполнении ${action}${errorCode} (день ${day}).`
  }
  if (event.event_type === 'session_action_executed') {
    const action = String(event.payload.action_type ?? 'действие')
    const mode = String(event.payload.execution_mode ?? '')
    return `Выполнено ${action} в режиме «${mode}» (день ${day}).`
  }
  if (event.event_type === 'session_action_simulated') {
    const action = String(event.payload.action_type ?? 'действие')
    return `Симулировано ${action} (день ${day}). Никаких сетевых вызовов не выполнено.`
  }
  if (event.event_type === 'micro_session_window_opened') return `Открыто окно микро-сессии (день ${day}).`
  if (event.event_type === 'micro_session_window_closed') return `Окно микро-сессии завершено (день ${day}).`
  if (event.event_type === 'circuit_breaker_tripped' || event.event_type === 'circuit_breaker_triggered') {
    const failures = event.payload.consecutive_failures !== undefined ? String(event.payload.consecutive_failures) : '?'
    return `Сессия поставлена на паузу после ${failures} последовательных ошибок.`
  }
  if (event.event_type === 'p2p_contact_recorded') {
    return `P2P-контакт с получателем зафиксирован (день ${day}).`
  }
  if (event.event_type === 'p2p_contact_recording_failed') {
    const error = event.payload.error ? ` Причина: ${String(event.payload.error)}` : ''
    return `Не удалось записать P2P-контакт (день ${day}).${error}`
  }
  if (event.event_type === 'isolation_claimed') return 'Аккаунт временно изолирован: сторонние модули не могут им управлять.'
  if (event.event_type === 'isolation_released') return 'Изоляция снята, аккаунт снова доступен другим модулям.'
  return JSON.stringify(event.payload)
}

export function formatWarmupDate(value: string | null): string {
  if (!value) return 'Не запланирован'
  return new Date(value).toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function formatWarmupNextStep(value: string | null, workersEnabled: boolean | undefined): string {
  if (!value) return 'Не запланирован'
  if (new Date(value).getTime() <= Date.now()) {
    return workersEnabled ? 'Готов к шагу сейчас' : 'Ждёт включения воркера'
  }
  return formatWarmupDate(value)
}

export function warmupProgressPercent(day: number, durationDays: number = 14): number {
  const denominator = Math.max(1, durationDays)
  return Math.min(100, Math.max(0, Math.round((day / denominator) * 100)))
}
