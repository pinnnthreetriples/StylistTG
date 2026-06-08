import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, test } from 'vitest'

import type { WarmupCycleConfig } from '../types'
import { WarmupCyclicStatus } from './WarmupCyclicStatus'
import { getWarmupCyclicStatusModel } from './WarmupCyclicStatusModel'

const cycleConfig: WarmupCycleConfig = {
  active_hours_total: 21,
  current_cycle: 3,
  days_total: 7,
  end_hour: 18,
  start_hour: 15,
  started_at: '2026-06-01T00:00:00Z',
}

describe('WarmupCyclicStatus', () => {
  test('renders active window state', () => {
    const model = getWarmupCyclicStatusModel(cycleConfig, new Date('2026-06-05T16:00:00Z'), 'UTC')

    expect(model).toEqual({
      headline: '🟢 Активно до 18:00',
      isActive: true,
      progress: 'День 3 из 7',
    })
  })

  test('renders waiting state after the daily window', () => {
    const model = getWarmupCyclicStatusModel(cycleConfig, new Date('2026-06-05T19:00:00Z'), 'UTC')

    expect(model).toEqual({
      headline: '⏸ Ожидаются активные часы — старт в 15:00 завтра',
      isActive: false,
      progress: 'День 3 из 7',
    })
  })

  test('renders status block markup', () => {
    const html = renderToStaticMarkup(
      <WarmupCyclicStatus cycleConfig={cycleConfig} now={new Date('2026-06-05T16:00:00Z')} timezone="UTC" />,
    )

    expect(html).toContain('Активно до 18:00')
    expect(html).toContain('День 3 из 7')
  })
})
