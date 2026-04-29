import { describe, expect, it } from 'vitest'

import { buildPreflightItems, formatCooldown } from '@/lib/settings'

describe('settings helpers', () => {
  it('formats cooldown seconds for settings UI', () => {
    expect(formatCooldown(0)).toBe('Выключено')
    expect(formatCooldown(30)).toBe('30 сек')
    expect(formatCooldown(120)).toBe('2 мин')
  })

  it('maps live preflight payload into status rows', () => {
    expect(
      buildPreflightItems({
        tdjson_present: true,
        tdlib_credentials_present: false,
        postgres_reachable: true,
        redis_reachable: false,
        storage_writable: true,
        rq_worker_expected: true,
        overall_status: 'degraded',
      }),
    ).toEqual([
      { key: 'tdjson', label: 'tdjson.dll', status: 'ok', message: 'Готов' },
      { key: 'tdlib_credentials', label: 'TDLib API', status: 'down', message: 'Недоступен' },
      { key: 'postgres', label: 'PostgreSQL', status: 'ok', message: 'Готов' },
      { key: 'redis', label: 'Redis', status: 'down', message: 'Недоступен' },
      { key: 'storage', label: 'Storage', status: 'ok', message: 'Готов' },
      { key: 'worker', label: 'RQ worker', status: 'ok', message: 'Требуется' },
      { key: 'overall', label: 'Live статус', status: 'attention', message: 'Ограничен' },
    ].map((item) => expect.objectContaining(item)))
  })
})
