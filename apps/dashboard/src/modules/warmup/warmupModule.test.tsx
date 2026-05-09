import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, test } from 'vitest'

import { WarmupReadinessBanner } from './components/WarmupReadinessBanner'
import type { WarmupReadiness } from './types'

const readiness: WarmupReadiness = {
  workers_enabled: false,
  dry_run: true,
  redis_connected: true,
  database_connected: true,
  active_sessions: 0,
  strategies_available: 3,
}

describe('warmup module UI helpers', () => {
  test('renders dry-run readiness banner without Telegram action promises', () => {
    const html = renderToStaticMarkup(<WarmupReadinessBanner readiness={readiness} />)

    expect(html).toContain('Безопасный режим')
    expect(html).toContain('Воркеры подготовки отключены')
    expect(html).toContain('не вызывает Telegram API')
  })

  test('renders live-mode readiness banner that does NOT promise no Telegram calls', () => {
    const liveReadiness: WarmupReadiness = {
      workers_enabled: true,
      dry_run: false,
      redis_connected: true,
      database_connected: true,
      active_sessions: 2,
      strategies_available: 3,
    }
    const html = renderToStaticMarkup(<WarmupReadinessBanner readiness={liveReadiness} />)

    expect(html).toContain('Выполнение включено')
    expect(html).toContain('Воркеры подготовки активны')
    expect(html).not.toContain('не вызывает Telegram API')
    expect(html).toContain('выполняют действия в Telegram')
    expect(html).toContain('Live-выполнение по расписанию')
  })

  test('renders undefined readiness as null (nothing rendered)', () => {
    const html = renderToStaticMarkup(<WarmupReadinessBanner readiness={undefined} />)
    expect(html).toBe('')
  })
})
