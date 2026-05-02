import { describe, expect, it } from 'vitest'

import { proxyErrorLabel, proxyStatusLabel, validateProxyInput } from '@/lib/proxy'

describe('proxy labels and validation', () => {
  it('maps proxy statuses to Russian labels', () => {
    expect(proxyStatusLabel(null)).toBe('Proxy: не назначен')
    expect(proxyStatusLabel('working')).toBe('TCP доступен')
    expect(proxyStatusLabel('tcp_working')).toBe('TCP доступен')
    expect(proxyStatusLabel('tdlib_working')).toBe('Telegram через proxy проверен')
    expect(proxyStatusLabel('tdlib_unverified')).toBe('Telegram через proxy не проверен')
    expect(proxyStatusLabel('failed')).toBe('Proxy: ошибка')
    expect(proxyStatusLabel('tdlib_failed')).toBe('TDLib через proxy не прошёл')
    expect(proxyStatusLabel('unknown')).toBe('Proxy: не проверен')
  })

  it('validates proxy host and port before upload', () => {
    expect(validateProxyInput({ proxy_type: 'socks5', host: '', port: 1080 })).toBe('Укажите host proxy')
    expect(validateProxyInput({ proxy_type: 'http', host: '127.0.0.1', port: 70000 })).toBe('Port должен быть от 1 до 65535')
    expect(validateProxyInput({ proxy_type: 'socks5', host: '127.0.0.1', port: 1080 })).toBeNull()
  })

  it('uses user-facing proxy error labels', () => {
    expect(proxyErrorLabel('proxy_timeout')).toBe('proxy не ответил вовремя')
    expect(proxyErrorLabel('proxy_connection_refused')).toBe('proxy отклонил подключение')
    expect(proxyErrorLabel('PROXY_CREDENTIALS_KEY_REQUIRED')).toBe(
      'Пароль proxy нельзя сохранить: не настроен ключ шифрования.',
    )
  })
})
