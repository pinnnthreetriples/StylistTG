import { newIdempotencyKey } from '@stylisttg/api-client'

export type ParsedOnboardingPhone = {
  phone_number: string
  label: string | null
  position: number
  raw: string
}

const PHONE_PATTERN = /\+?\d[\d\s().-]{7,}\d/g

export function parseOnboardingPhones(rawInput: string, defaultLabel = ''): ParsedOnboardingPhone[] {
  const rows: ParsedOnboardingPhone[] = []
  const fallbackLabel = defaultLabel.trim() || null
  for (const line of rawInput.split(/\r?\n/)) {
    const matches = Array.from(line.matchAll(PHONE_PATTERN))
    for (const match of matches) {
      const normalized = normalizePhoneToken(match[0])
      if (!normalized) continue
      const hasMultiplePhones = matches.length > 1
      const trailing = line.slice((match.index ?? 0) + match[0].length).trim()
      const label = hasMultiplePhones || looksLikePhone(trailing) ? fallbackLabel : trailing.replace(/^[;\t,\s-]+/, '').trim() || fallbackLabel
      rows.push({
        phone_number: normalized,
        label,
        position: rows.length,
        raw: match[0],
      })
    }
  }
  return rows
}

export function makeOnboardingKey(prefix: string): string {
  return `${prefix}-${newIdempotencyKey()}`
}

export function canConfirmOnboardingBatch(
  batchStatus: string,
  consentAccepted: boolean,
  busy: boolean,
): boolean {
  return batchStatus === 'preview_ready' && consentAccepted && !busy
}

export function isTerminalOnboardingBatchStatus(status: string): boolean {
  return ['completed', 'failed', 'cancelled', 'expired', 'requires_reauth'].includes(status)
}

export function onboardingStatusLabel(status: string): string {
  return ({
    created: 'Создан',
    uploaded: 'Файл загружен',
    validating: 'Проверка',
    preview_ready: 'Готово к подтверждению',
    confirmed: 'Подтверждено',
    queued: 'В очереди',
    running: 'Выполняется',
    partially_completed: 'Частично готово',
    completed: 'Готово',
    requires_reauth: 'Нужна ручная авторизация',
    pending: 'Ожидает проверки',
    valid: 'Можно добавить',
    duplicate: 'Дубликат',
    existing: 'Уже есть',
    unsupported: 'Не поддерживается',
    blocked: 'Заблокировано',
    starting_auth: 'Запуск авторизации',
    waiting_code: 'Ожидает код Telegram',
    waiting_2fa: 'Ожидает пароль 2FA',
    importing_session: 'Импорт сессии',
    checking_session: 'Проверка сессии',
    ready: 'Готов',
    failed: 'Ошибка',
    cancelled: 'Отменено',
    expired: 'Истекло',
  } as Record<string, string>)[status] ?? status
}

export function onboardingSourceLabel(sourceType: string): string {
  return ({
    phone: 'Номера',
    phone_bulk: 'Номера',
    json_metadata: 'JSON-метаданные',
    tdlib_directory: 'TDLib',
    tdata_archive: 'tdata',
    session_file: 'Файл сессии',
    reauth: 'Повторная авторизация',
  } as Record<string, string>)[sourceType] ?? sourceType
}

export function onboardingRiskLabel(risk: string): string {
  return ({ low: 'Низкий', medium: 'Средний', high: 'Высокий' } as Record<string, string>)[risk] ?? risk
}

function normalizePhoneToken(value: string): string | null {
  const digits = value.replace(/\D/g, '')
  if (digits.length < 10) return null
  return `+${digits}`
}

function looksLikePhone(value: string): boolean {
  return /\+?\d[\d\s().-]{7,}\d/.test(value)
}
