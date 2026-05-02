const stepLabels: Record<string, string> = {
  set_name: 'Имя',
  set_bio: 'Описание',
  set_username: 'Юзернейм',
  set_profile_photo: 'Фото профиля',
  upload_profile_audio: 'Загрузка музыки',
  add_profile_audio: 'Музыка профиля',
  remove_profile_audio: 'Удаление музыки',
  keep_profile_audio: 'Музыка без изменений',
  validate_story_capabilities: 'Проверка историй',
  prepare_story_media: 'Подготовка истории',
  post_story_image: 'Новая история с фото',
  post_story_video: 'Новая история с видео',
}

const jobStateLabels: Record<string, string> = {
  queued: 'В очереди',
  waiting_lock: 'Ожидает аккаунт',
  running: 'В работе',
  completed: 'Готово',
  partially_completed: 'Частично готово',
  failed: 'Ошибка',
  manual_intervention_needed: 'Нужна ручная проверка',
  canceled: 'Отменено',
  dedup_blocked: 'Повтор уже есть',
  draft: 'Черновик',
}

const stepStatusLabels: Record<string, string> = {
  planned: 'Запланировано',
  not_started: 'Не запускалось',
  started: 'В работе',
  succeeded: 'Готово',
  failed: 'Ошибка',
  uncertain: 'Проверить',
  skipped: 'Пропущено',
}

const errorLabels: Record<string, string> = {
  ACCOUNT_NOT_FOUND: 'Аккаунт не найден',
  AUTH_MANUAL_INTERVENTION_REQUIRED: 'Нужна ручная проверка аккаунта',
  AUTH_BATCH_EMPTY: 'В пачке нет новых аккаунтов',
  AUTH_BATCH_ITEM_NOT_FOUND: 'Аккаунт в пачке не найден',
  AUTH_BATCH_NOT_FOUND: 'Пачка авторизации не найдена',
  AUTH_BATCH_STATE_CONFLICT: 'Действие недоступно для текущего состояния пачки',
  AUTH_COOLDOWN_ACTIVE: 'Сработала пауза перед повторным входом',
  AUTH_DAILY_LIMIT_REACHED: 'Достигнут дневной лимит попыток входа',
  DEDUP_BLOCKED: 'Такая задача уже есть',
  FLOOD_WAIT: 'Telegram временно ограничил попытки входа',
  JOB_ACTIVE_CANNOT_DELETE: 'Сначала отмените активную задачу',
  JOB_NOT_FOUND: 'Задача не найдена',
  JOB_RUNNING_CANNOT_CANCEL: 'Задача уже выполняется, дождитесь завершения или сработки таймаута',
  NETWORK_ERROR: 'Нет связи с backend',
  QUEUE_UNAVAILABLE: 'Очередь задач недоступна',
  PROFILE_JOB_QUEUE_UNAVAILABLE: 'Очередь задач недоступна',
  PHONE_CODE_EXPIRED: 'Код Telegram истёк. Запросите новый код',
  PHONE_CODE_INVALID: 'Неверный код Telegram',
  PHONE_NUMBER_BANNED: 'Telegram заблокировал этот номер',
  PHONE_NUMBER_INVALID: 'Telegram не принял этот номер',
  PASSWORD_HASH_INVALID: 'Неверный пароль 2FA',
  PRODUCTION_TDLIB_AUTH_DISABLED: 'Авторизация в обычном Telegram выключена в настройках backend',
  RUNTIME_UNUSABLE: 'Аккаунт пока не готов к работе',
  FROZEN_METHOD_INVALID: 'Telegram ограничил это действие',
  STORY_CAPABILITY_BLOCKED: 'Истории сейчас недоступны',
  STORY_ASSET_NOT_READY: 'Черновик истории устарел. Обновите страницу или удалите историю из черновика',
  STORY_DELETE_FAILED: 'Telegram не удалил историю',
  STORY_POST_CANNOT_DELETE: 'Эту историю нельзя удалить из приложения',
  STORY_POST_FAILED: 'Telegram не опубликовал историю',
  STORY_TELEGRAM_REJECTED: 'Telegram отклонил публикацию истории',
  STORY_POST_NOT_FOUND: 'История не найдена',
  STORY_PRIVACY_PRESET_UNSUPPORTED: 'Этот режим приватности истории не поддерживается',
  STORIES_DISABLED: 'Истории выключены в настройках приложения',
  STORIES_TDLIB_LIVE_DISABLED: 'Публикация историй через TDLib пока выключена',
  CAN_POST_STORY_PREMIUM_NEEDED: 'Для публикации истории нужен Premium',
  CAN_POST_STORY_ACTIVE_STORY_LIMIT_EXCEEDED:
    'Лимит активных историй для обычного аккаунта. Удалите одну историю, дождитесь окончания или используйте Premium с повышенным лимитом',
  CAN_POST_STORY_WEEKLY_LIMIT_EXCEEDED: 'Достигнут недельный лимит историй. Приобретите Premium',
  CAN_POST_STORY_UNKNOWN: 'Telegram сейчас не разрешил публикацию истории',
  story_post_confirmation_timeout: 'Telegram не подтвердил публикацию истории',
  UNSUPPORTED_AUTH_BRANCH: 'Этот способ входа пока не поддерживается',
  UPLOAD_TOO_LARGE: 'Файл слишком большой',
  USERNAME_INVALID: 'Юзернейм некорректен',
  USERNAME_OCCUPIED: 'Юзернейм уже занят',
  USERNAME_PURCHASE_AVAILABLE: 'Юзернейм доступен только через покупку',
  USERNAME_AMBIGUOUS: 'Юзернейм требует проверки',
  tdlib_error: 'Telegram не принял изменение',
  TdlibProfileQueryError: 'TDLib не смог применить изменение профиля',
  TdlibUnavailable: 'TDLib сейчас недоступен',
  TDLIB_GET_ME_MISSING_ID: 'TDLib не вернул идентификатор аккаунта',
  TDLIB_SAVED_MESSAGES_CHAT_MISSING_ID: 'TDLib не вернул чат для подготовки музыки',
  TDLIB_UNSUPPORTED_UPLOAD_FILE_METHOD: 'Использовался неподдерживаемый способ загрузки музыки',
  TDLIB_AUTH_ERROR: 'TDLib не завершил авторизацию',
  tdlib_profile_step_failed: 'Telegram не применил шаг профиля',
  PROFILE_AUDIO_UPLOAD_NOT_COMPLETED: 'Telegram не подтвердил загрузку музыки',
  PROFILE_AUDIO_ADD_FAILED: 'Telegram не добавил музыку в профиль',
  PROFILE_AUDIO_REMOVE_FAILED: 'Telegram не удалил музыку из профиля',
  PROFILE_AUDIO_MESSAGE_SEND_FAILED: 'Telegram не смог подготовить музыку профиля',
  PROFILE_AUDIO_MESSAGE_SEND_TIMEOUT: 'Telegram не подтвердил подготовку музыки',
  PROFILE_AUDIO_FILE_ID_MISSING: 'Telegram не вернул файл музыки',
  PROFILE_AUDIO_UNSUPPORTED_FORMAT: 'Для музыки профиля нужен MP3 или M4A',
  profile_runtime_failed: 'Runtime профиля завершился с ошибкой',
  worker_timeout: 'Worker не завершил задачу вовремя',
  worker_or_child_interrupted: 'Выполнение было прервано',
  profile_job_cooldown_active: 'Сработала пауза между запусками задач',
  'cooldown_active:profile_update': 'Профиль временно на паузе безопасности',
  'cooldown_active:username': 'Username временно на паузе безопасности',
  'cooldown_active:profile_photo': 'Фото профиля временно на паузе безопасности',
  'cooldown_active:profile_music': 'Музыка профиля временно на паузе безопасности',
  'cooldown_active:story_post': 'Публикация историй временно на паузе безопасности',
  'cooldown_active:story_delete': 'Удаление историй временно на паузе безопасности',
  'cooldown_active:sync': 'Синхронизация временно на паузе безопасности',
  'cooldown_active:batch_operation': 'Пакетные действия временно на паузе безопасности',
  account_not_execution_usable: 'Аккаунт сейчас не готов к выполнению задач',
  profile_sync_unknown: 'Профиль ещё не синхронизирован',
  stale_profile_sync: 'Профиль давно не синхронизировался',
  recent_partial_job: 'Недавно задача завершилась частично',
  recent_failed_job: 'Недавно задача завершилась ошибкой',
  recent_flood_wait: 'Недавно была ошибка FLOOD_WAIT',
  username_recently_rejected: 'Недавно Telegram отклонил юзернейм',
  music_capability_not_checked: 'Музыка профиля ещё не проверена',
  fresh_validity_required: 'Перед live-запуском нужна свежая проверка аккаунта',
  fresh_validity_stale: 'Проверка аккаунта устарела',
  stories_live_disabled: 'Публикация историй пока выключена',
  stories_disabled: 'Истории выключены в настройках приложения',
  stories_mock_mode: 'Публикация историй недоступна в mock-режиме',
  no_known_story_posts: 'Нет известных приложению активных историй',
  ready: 'Готов к работе',
  broken: 'Есть проблема',
  closed: 'Сессия закрыта',
  manual_intervention_needed: 'Нужна ручная проверка',
  missing_tdlib_credentials: 'Не настроены TDLib API ID/API hash',
  unexpected_auth_state: 'Неожиданное состояние авторизации',
  stories_live_TDLib_execution_is_not_enabled: 'Публикация историй через TDLib пока выключена',
  stories_are_disabled: 'Истории выключены в настройках приложения',
  stories_live_TDLib_publishing_requires_TDLib_profile_execution:
    'Публикация историй будет доступна после включения TDLib-исполнения профиля',
  'stories_live_TDLib_publishing_is_disabled': 'Публикация историй пока выключена',
  'story_video_preparation_is_limited_until_ffprobe_and_ffmpeg_are_available':
    'Видео проверяется в ограниченном режиме без ffmpeg/ffprobe',
}

export function labelStep(value: string | null | undefined): string {
  if (!value) {
    return 'Шаг не указан'
  }

  const normalized = normalizeKey(value)
  const storyLabel = labelDynamicStoryStep(normalized)
  if (storyLabel) {
    return storyLabel
  }

  return stepLabels[normalized] ?? sentenceCase(normalized)
}

export function labelJobState(value: string | null | undefined): string {
  return labelFromMap(value, jobStateLabels, 'Статус')
}

export function labelStepStatus(value: string | null | undefined): string {
  return labelFromMap(value, stepStatusLabels, 'Статус')
}

export function labelIssue(value: string | null | undefined): string {
  return labelFromMap(value, errorLabels, 'Проблема')
}

export function labelBlockingItem(value: string): string {
  return labelIssue(normalizeKey(value))
}

export function labelStoryCapabilityWarning(value: string): string {
  return labelIssue(normalizeKey(value))
}

function labelFromMap(
  value: string | null | undefined,
  labels: Record<string, string>,
  fallbackPrefix: string,
): string {
  if (!value) {
    return `${fallbackPrefix} не указан`
  }
  const normalized = normalizeKey(value)
  return labels[normalized] ?? sentenceCase(normalized)
}

function normalizeKey(value: string): string {
  return value.trim().replace(/\s+/g, '_')
}

function sentenceCase(value: string): string {
  const readable = value.replace(/[_-]+/g, ' ').trim()
  if (!readable) {
    return 'Неизвестно'
  }
  return readable[0].toUpperCase() + readable.slice(1)
}

function labelDynamicStoryStep(value: string): string | null {
  const match = /^story_(\d+)_(validate_capabilities|prepare_media|post)$/.exec(value)
  if (!match) {
    return null
  }

  const storyNumber = match[1]
  const action = match[2]
  const actionLabel =
    action === 'validate_capabilities'
      ? 'Проверка'
      : action === 'prepare_media'
        ? 'Подготовка'
        : 'Публикация'

  return `История ${storyNumber} · ${actionLabel}`
}
