export type ProxyStatus =
  | 'none'
  | 'unknown'
  | 'working'
  | 'tcp_working'
  | 'tdlib_working'
  | 'tdlib_unverified'
  | 'failed'
  | 'tdlib_failed'
  | string
export type ProxyType = 'socks5' | 'http'

export type AccountProxy = {
  account_id: string
  proxy_type: ProxyType | string
  host: string
  port: number
  username: string | null
  has_password: boolean
  status: ProxyStatus
  last_checked_at: string | null
  last_check_scope: 'tcp' | 'tcp_tdlib' | string | null
  last_error_code: string | null
  last_error_message: string | null
  tdlib_verified_at: string | null
  tdlib_last_error_code: string | null
  tdlib_last_error_message: string | null
  created_at: string
  updated_at: string
}

export type AccountProxyInput = {
  proxy_type: ProxyType
  host: string
  port: number
  username?: string | null
  password?: string | null
}

export type AccountProxySummary = {
  account_id: string
  status: ProxyStatus
  proxy_type: ProxyType | string | null
  host: string | null
  port: number | null
  last_checked_at: string | null
  last_check_scope: 'tcp' | 'tcp_tdlib' | string | null
  last_error_code: string | null
  tdlib_verified_at: string | null
  tdlib_last_error_code: string | null
}

export function proxyStatusLabel(status: ProxyStatus | null | undefined): string {
  if (!status || status === 'none') return 'Прокси не назначен'
  if (status === 'working' || status === 'tcp_working') return 'TCP доступен'
  if (status === 'tdlib_working') return 'Telegram через прокси проверен'
  if (status === 'tdlib_unverified') return 'Telegram через прокси не проверен'
  if (status === 'failed') return 'Прокси: ошибка'
  if (status === 'tdlib_failed') return 'Проверка Telegram через прокси не прошла'
  return 'Прокси не проверен'
}

export function proxyStatusTone(status: ProxyStatus | null | undefined): 'green' | 'amber' | 'red' | 'gray' {
  if (status === 'working' || status === 'tcp_working' || status === 'tdlib_working') return 'green'
  if (status === 'failed' || status === 'tdlib_failed') return 'red'
  if (status === 'unknown' || status === 'tdlib_unverified') return 'amber'
  return 'gray'
}

export function proxyErrorLabel(code: string | null | undefined): string {
  if (!code) return ''
  const labels: Record<string, string> = {
    proxy_timeout: 'прокси не ответил вовремя',
    proxy_auth_failed: 'ошибка логина или пароля прокси',
    proxy_connection_refused: 'прокси отклонил подключение',
    proxy_dns_failed: 'хост прокси не найден',
    proxy_unsupported: 'тип прокси не поддерживается',
    proxy_connection_failed: 'не удалось подключиться к прокси',
    PROXY_CREDENTIALS_KEY_REQUIRED: 'Пароль прокси нельзя сохранить: не настроен ключ шифрования.',
    PROXY_CREDENTIALS_CRYPTO_UNAVAILABLE: 'Пароль прокси нельзя сохранить: зависимость backend для шифрования не установлена.',
  }
  return labels[code] ?? 'ошибка прокси'
}

export function validateProxyInput(input: AccountProxyInput): string | null {
  if (!['socks5', 'http'].includes(input.proxy_type)) return 'Поддерживаются только SOCKS5 и HTTP прокси'
  if (!input.host.trim()) return 'Укажите хост прокси'
  if (!Number.isInteger(input.port) || input.port < 1 || input.port > 65535) return 'Порт должен быть от 1 до 65535'
  return null
}
