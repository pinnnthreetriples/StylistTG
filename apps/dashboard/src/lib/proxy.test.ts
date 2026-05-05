import { describe, expect, it } from 'vitest'

import { proxyErrorLabel, proxyStatusLabel, validateProxyInput } from '@/lib/proxy'

describe('proxy labels and validation', () => {
  it('maps proxy statuses to Russian labels', () => {
    expect(proxyStatusLabel(null)).toBe('Прокси не назначен')
    expect(proxyStatusLabel('working')).toBe('TCP доступен')
    expect(proxyStatusLabel('tcp_working')).toBe('TCP доступен')
    expect(proxyStatusLabel('tdlib_working')).toBe('Telegram через прокси проверен')
    expect(proxyStatusLabel('tdlib_unverified')).toBe('Telegram через прокси не проверен')
    expect(proxyStatusLabel('failed')).toBe('Прокси: ошибка')
    expect(proxyStatusLabel('tdlib_failed')).toBe('Проверка Telegram через прокси не прошла')
    expect(proxyStatusLabel('unknown')).toBe('Прокси не проверен')
  })

  it('validates proxy host and port before upload', () => {
    expect(validateProxyInput({ proxy_type: 'socks5', host: '', port: 1080 })).toBe('Укажите хост прокси')
    expect(validateProxyInput({ proxy_type: 'http', host: '127.0.0.1', port: 70000 })).toBe('Порт должен быть от 1 до 65535')
    expect(validateProxyInput({ proxy_type: 'socks5', host: '127.0.0.1', port: 1080 })).toBeNull()
  })

  it('uses user-facing proxy error labels', () => {
    expect(proxyErrorLabel('proxy_timeout')).toBe('прокси не ответил вовремя')
    expect(proxyErrorLabel('proxy_connection_refused')).toBe('прокси отклонил подключение')
    expect(proxyErrorLabel('PROXY_CREDENTIALS_KEY_REQUIRED')).toBe(
      'Пароль прокси нельзя сохранить: не настроен ключ шифрования.',
    )
  })
})
