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
  if (!status || status === 'none') return 'Proxy: не назначен'
  if (status === 'working' || status === 'tcp_working') return 'TCP доступен'
  if (status === 'tdlib_working') return 'Telegram через proxy проверен'
  if (status === 'tdlib_unverified') return 'Telegram через proxy не проверен'
  if (status === 'failed') return 'Proxy: ошибка'
  if (status === 'tdlib_failed') return 'TDLib через proxy не прошёл'
  return 'Proxy: не проверен'
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
    proxy_timeout: 'proxy не ответил вовремя',
    proxy_auth_failed: 'ошибка логина или пароля proxy',
    proxy_connection_refused: 'proxy отклонил подключение',
    proxy_dns_failed: 'host proxy не найден',
    proxy_unsupported: 'тип proxy не поддерживается',
    proxy_connection_failed: 'не удалось подключиться к proxy',
    PROXY_CREDENTIALS_KEY_REQUIRED: 'Пароль proxy нельзя сохранить: не настроен ключ шифрования.',
    PROXY_CREDENTIALS_CRYPTO_UNAVAILABLE: 'Пароль proxy нельзя сохранить: backend dependency для шифрования не установлена.',
  }
  return labels[code] ?? 'ошибка proxy'
}

export function validateProxyInput(input: AccountProxyInput): string | null {
  if (!['socks5', 'http'].includes(input.proxy_type)) return 'Поддерживаются только SOCKS5 и HTTP proxy'
  if (!input.host.trim()) return 'Укажите host proxy'
  if (!Number.isInteger(input.port) || input.port < 1 || input.port > 65535) return 'Port должен быть от 1 до 65535'
  return null
}
