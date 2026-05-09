import * as Sentry from '@sentry/react'

const SENSITIVE_EXACT_KEYS = new Set([
  'authorization',
  'cookie',
  'cookies',
  'database_url',
  'databaseurl',
  'dsn',
  'jwt',
  'otp',
  'otp_code',
  'otpcode',
  'phone',
  'redis_url',
  'redisurl',
  'request_body',
  'requestbody',
  'secret',
  'service_role',
  'servicerole',
  'session',
  'token',
])

declare global {
  interface Window {
    __STYLISTTG_CAPTURE_TEST_ERROR__?: () => Promise<void>
  }
}

export function initObservability() {
  const dsn = import.meta.env.VITE_BETTER_STACK_DASHBOARD_DSN
  if (!dsn) {
    installDevTestCommand(false)
    return false
  }

  Sentry.init({
    dsn,
    environment: import.meta.env.VITE_APP_ENV,
    release: import.meta.env.VITE_SENTRY_RELEASE,
    sendDefaultPii: false,
    tracesSampleRate: 0,
    replaysSessionSampleRate: 0,
    replaysOnErrorSampleRate: 0,
    beforeSend: (event) => sanitizeEvent(event),
  })
  installDevTestCommand(true)
  return true
}

function installDevTestCommand(enabled: boolean) {
  if (!import.meta.env.DEV || typeof window === 'undefined') return
  window.__STYLISTTG_CAPTURE_TEST_ERROR__ = async () => {
    if (!enabled) {
      throw new Error('StylistTG frontend observability is not configured')
    }
    Sentry.captureException(new Error('StylistTG frontend observability test error'))
    await Sentry.flush(2000)
  }
}

function sanitizeEvent(event: Sentry.ErrorEvent): Sentry.ErrorEvent {
  return sanitizeValue(event) as Sentry.ErrorEvent
}

function sanitizeValue(value: unknown, key?: string): unknown {
  if (key && isSensitiveKey(key)) return filteredValue(value)
  if (typeof value === 'string') return redactText(value)
  if (Array.isArray(value)) return value.map((item) => sanitizeValue(item))
  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value).map(([entryKey, entryValue]) => [
        entryKey,
        sanitizeValue(entryValue, entryKey),
      ]),
    )
  }
  return value
}

function redactText(value: string): string {
  return value
    .replace(/([a-z][a-z0-9+.-]*:\/\/)([^:/@\s]+):([^@\s]+)@/gi, '$1[Filtered]:[Filtered]@')
    .replace(
      /\b(password|token|jwt|secret|api_hash|auth_code|authcode|otp_code|otp|phone|proxy_password)\b(\s*[:=]\s*)[^\s,;]+/gi,
      '$1$2[Filtered]',
    )
}

function filteredValue(value: unknown): unknown {
  if (Array.isArray(value)) return ['[Filtered]']
  if (value && typeof value === 'object') return { filtered: true }
  return '[Filtered]'
}

function isSensitiveKey(key: string): boolean {
  const normalized = key.toLowerCase()
  const compact = normalized.replace(/[^a-z0-9]/g, '')
  const words = keyWords(key)
  const wordSet = new Set(words)

  if (SENSITIVE_EXACT_KEYS.has(normalized) || SENSITIVE_EXACT_KEYS.has(compact)) return true
  if (words.length === 0) return false
  if (['sessionid', 'sessiontoken', 'sessioncookie'].includes(compact)) return true
  if (['password', 'token', 'jwt', 'secret'].some((word) => wordSet.has(word))) return true
  if (containsWordSequence(words, ['api', 'hash'])) return true
  if (containsWordSequence(words, ['auth', 'code'])) return true
  if (containsWordSequence(words, ['two', 'factor', 'password'])) return true
  if (wordSet.has('phone')) return true
  if (wordSet.has('dsn') && words[words.length - 1] === 'dsn') return true
  if (
    wordSet.has('tdlib') &&
    ['path', 'root', 'directory', 'database', 'files', 'session', 'library'].some((word) =>
      wordSet.has(word),
    )
  ) {
    return true
  }
  if (
    wordSet.has('telegram') &&
    ['api', 'hash', 'phone', 'session', 'token', 'password'].some((word) => wordSet.has(word))
  ) {
    return true
  }
  if (
    ['s3', 'b2', 'supabase'].some((word) => wordSet.has(word)) &&
    ['access', 'key', 'secret', 'token', 'password', 'role', 'jwt'].some((word) =>
      wordSet.has(word),
    )
  ) {
    return true
  }
  return false
}

function keyWords(key: string): string[] {
  return key
    .replace(/([a-z0-9])([A-Z])/g, '$1_$2')
    .toLowerCase()
    .split(/[^a-z0-9]+/)
    .filter(Boolean)
}

function containsWordSequence(words: string[], sequence: string[]): boolean {
  if (words.length < sequence.length) return false
  return words.some((_, index) =>
    sequence.every((word, sequenceIndex) => words[index + sequenceIndex] === word),
  )
}
