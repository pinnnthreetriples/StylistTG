import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, test } from 'vitest'

import type { WarmupStrategy } from '../types'
import { WarmupDailyCountersPanel } from './WarmupDailyCountersPanel'

const strategy: WarmupStrategy = {
  id: 'strategy-1',
  name: 'Shadow standard',
  description: null,
  is_preset: false,
  preset_kind: 'standard',
  execution_mode: 'shadow',
  duration_days: 3,
  daily_action_limits: {
    '1': { feed_read: 2, join_chat: 0, p2p_send: 0 },
    '2': { feed_read: 2, join_chat: 1, p2p_send: 0 },
    '3': { feed_read: 2, join_chat: 1, p2p_send: 1 },
  },
  session_window_config: {},
  ui_summary: {},
}

describe('WarmupDailyCountersPanel', () => {
  test('renders all action types from strategy plan as table columns', () => {
    const html = renderToStaticMarkup(
      <WarmupDailyCountersPanel
        currentDay={1}
        durationDays={3}
        dailyCounters={{ '0': { feed_read: 2 }, '1': { feed_read: 1 } }}
        strategy={strategy}
      />,
    )

    expect(html).toContain('feed_read')
    expect(html).toContain('join_chat')
    expect(html).toContain('p2p_send')
  })

  test('shows actual / planned cells using daily_action_limits as denominator', () => {
    const html = renderToStaticMarkup(
      <WarmupDailyCountersPanel
        currentDay={1}
        durationDays={3}
        dailyCounters={{ '0': { feed_read: 2 }, '1': { feed_read: 1 } }}
        strategy={strategy}
      />,
    )

    // day 0: actual feed_read 2 / plan 2 (plan key "1")
    expect(html).toMatch(/2<[^>]+>\/2/)
    // day 1: actual feed_read 1 / plan 2 (plan key "2")
    expect(html).toMatch(/1<[^>]+>\/2/)
  })

  test('renders fallback message when neither plan nor counters exist', () => {
    const html = renderToStaticMarkup(
      <WarmupDailyCountersPanel
        currentDay={0}
        durationDays={3}
        dailyCounters={{}}
        strategy={null}
      />,
    )
    expect(html).toContain('План пока не содержит действий')
  })

  test('does not render a day beyond the configured duration for completed sessions', () => {
    const html = renderToStaticMarkup(
      <WarmupDailyCountersPanel
        currentDay={3}
        durationDays={3}
        dailyCounters={{
          '0': { feed_read: 2 },
          '1': { feed_read: 2 },
          '2': { feed_read: 2 },
        }}
        strategy={strategy}
      />,
    )

    expect(html).toMatch(/>1<\/td>/)
    expect(html).toMatch(/>2<\/td>/)
    expect(html).toMatch(/>3<\/td>/)
    expect(html).not.toMatch(/>4<\/td>/)
  })
})
