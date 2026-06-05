import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, test } from 'vitest'

import { WarmupSummaryCards } from './WarmupSummaryCards'
import { formatWarmupSummaryDuration } from './WarmupStatusPillModel'

describe('WarmupSummaryCards', () => {
  test('duration formatting', () => {
    expect(formatWarmupSummaryDuration(30 * 60)).toBe('30мин')
    expect(formatWarmupSummaryDuration(60 * 60)).toBe('1ч')
    expect(formatWarmupSummaryDuration(2 * 60 * 60)).toBe('2ч')
    expect(formatWarmupSummaryDuration(24 * 60 * 60)).toBe('1д')
    expect(formatWarmupSummaryDuration(3 * 24 * 60 * 60)).toBe('3д')
  })

  test('short run snapshot', () => {
    expect(
      renderToStaticMarkup(
        <WarmupSummaryCards accountCount={3} durationSeconds={30 * 60} status="RUNNING" />,
      ),
    ).toMatchSnapshot()
  })

  test('multi-day live snapshot', () => {
    expect(
      renderToStaticMarkup(
        <WarmupSummaryCards
          accountCount={12}
          durationSeconds={2 * 24 * 60 * 60}
          status="LIVE"
          lastHeartbeatAt="2026-06-05T10:00:00Z"
          now={new Date('2026-06-05T10:00:10Z')}
        />,
      ),
    ).toMatchSnapshot()
  })
})
