import { describe, expect, it } from 'vitest'

import { getHomeApiReadinessStatus } from './readinessStatus'

describe('getHomeApiReadinessStatus', () => {
  it('marks API green only for explicit ok readiness', () => {
    expect(getHomeApiReadinessStatus({ status: 'ok' }, false)).toEqual({ tone: 'green', label: 'Работает' })
    expect(getHomeApiReadinessStatus({ status: 'unavailable' }, false)).toEqual({ tone: 'red', label: 'Недоступен' })
    expect(getHomeApiReadinessStatus({ status: 'degraded' }, false)).toEqual({ tone: 'red', label: 'Недоступен' })
  })

  it('distinguishes loading from request errors', () => {
    expect(getHomeApiReadinessStatus(undefined, false)).toEqual({ tone: 'muted', label: 'Проверка...' })
    expect(getHomeApiReadinessStatus({ status: 'ok' }, true)).toEqual({ tone: 'red', label: 'Недоступен' })
  })
})
