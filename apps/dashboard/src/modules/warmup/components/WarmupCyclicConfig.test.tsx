import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, test } from 'vitest'

import { WarmupCyclicConfig } from './WarmupCyclicConfig'
import { buildWarmupCyclePreview, validateWarmupCycleConfig } from './WarmupCyclicConfigModel'

describe('WarmupCyclicConfig', () => {
  test('renders enabled fields and live preview', () => {
    const html = renderToStaticMarkup(
      <WarmupCyclicConfig
        daysTotal={7}
        enabled
        endHour={18}
        startHour={15}
        onDaysTotalChange={() => undefined}
        onEnabledChange={() => undefined}
        onEndHourChange={() => undefined}
        onStartHourChange={() => undefined}
      />,
    )

    expect(html).toContain('Циклический режим')
    expect(html).toContain('Начало')
    expect(html).toContain('Конец')
    expect(html).toContain('Дней')
    expect(html).toContain('Будет прогреваться 7 дней × 3ч = 21ч активности')
  })

  test('rejects overnight windows', () => {
    const validation = validateWarmupCycleConfig({
      daysTotal: 7,
      enabled: true,
      endHour: 2,
      startHour: 22,
    })

    expect(validation.isValid).toBe(false)
    expect(validation.errors.endHour).toContain('Ночные окна пока не поддерживаются')
  })

  test('rejects days outside 1-30', () => {
    const validation = validateWarmupCycleConfig({
      daysTotal: 31,
      enabled: true,
      endHour: 18,
      startHour: 15,
    })

    expect(validation.isValid).toBe(false)
    expect(validation.errors.daysTotal).toBe('Дней должно быть от 1 до 30.')
  })

  test('renders inline error for invalid days', () => {
    const html = renderToStaticMarkup(
      <WarmupCyclicConfig
        daysTotal={31}
        enabled
        endHour={18}
        startHour={15}
        onDaysTotalChange={() => undefined}
        onEnabledChange={() => undefined}
        onEndHourChange={() => undefined}
        onStartHourChange={() => undefined}
      />,
    )

    expect(html).toContain('Дней должно быть от 1 до 30.')
  })

  test('builds preview formula', () => {
    expect(
      buildWarmupCyclePreview({
        daysTotal: 10,
        enabled: true,
        endHour: 13,
        startHour: 10,
      }),
    ).toBe('Будет прогреваться 10 дней × 3ч = 30ч активности')
  })
})
