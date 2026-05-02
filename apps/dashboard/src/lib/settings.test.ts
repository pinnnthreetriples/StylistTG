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
        rq_worker_status: 'unknown',
        profile_worker_status: 'unknown',
        auth_worker_status: 'unknown',
        overall_status: 'degraded',
      }),
    ).toEqual([
      { key: 'tdjson', label: 'tdjson.dll', status: 'ok', message: 'Готов' },
      { key: 'tdlib_credentials', label: 'TDLib API', status: 'down', message: 'Недоступен' },
      { key: 'postgres', label: 'PostgreSQL', status: 'ok', message: 'Готов' },
      { key: 'redis', label: 'Redis', status: 'down', message: 'Недоступен' },
      { key: 'storage', label: 'Storage', status: 'ok', message: 'Готов' },
      { key: 'profile_worker', label: 'Profile worker', status: 'attention', message: 'Worker нужен для выполнения задач' },
      { key: 'auth_worker', label: 'Auth worker', status: 'attention', message: 'Worker нужен для выполнения задач' },
      { key: 'overall', label: 'Live статус', status: 'attention', message: 'Ограничен' },
    ].map((item) => expect.objectContaining(item)))
  })

  it('shows ready worker only when backend confirms an active RQ worker', () => {
    const items = buildPreflightItems({
      tdjson_present: true,
      tdlib_credentials_present: true,
      postgres_reachable: true,
      redis_reachable: true,
      storage_writable: true,
      rq_worker_expected: true,
      rq_worker_status: 'ready',
      profile_worker_status: 'ready',
      auth_worker_status: 'ready',
      overall_status: 'ok',
    })

    expect(items.find((item) => item.key === 'profile_worker')).toEqual(
      expect.objectContaining({ status: 'ok', message: 'Готов' }),
    )
    expect(items.find((item) => item.key === 'auth_worker')).toEqual(
      expect.objectContaining({ status: 'ok', message: 'Готов' }),
    )
  })

  it('shows missing worker with the manual start command', () => {
    const items = buildPreflightItems({
      tdjson_present: true,
      tdlib_credentials_present: true,
      postgres_reachable: true,
      redis_reachable: true,
      storage_writable: true,
      rq_worker_expected: true,
      rq_worker_status: 'missing',
      profile_worker_status: 'missing',
      auth_worker_status: 'missing',
      overall_status: 'degraded',
    })

    expect(items.find((item) => item.key === 'profile_worker')).toEqual(
      expect.objectContaining({
        status: 'down',
        message: 'Worker не запущен',
        help: expect.stringContaining('python -m rq.cli worker profile_jobs'),
      }),
    )
    expect(items.find((item) => item.key === 'auth_worker')).toEqual(
      expect.objectContaining({
        status: 'down',
        message: 'Worker не запущен',
        help: expect.stringContaining('python -m rq.cli worker auth_jobs'),
      }),
    )
  })
})
