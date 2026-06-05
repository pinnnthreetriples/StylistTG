import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, test } from 'vitest'

import type { WarmupSessionTimer as WarmupSessionTimerData } from '../types'
import { WarmupSessionTimer } from './WarmupSessionTimer'
import { formatTimerText } from './WarmupSessionTimerModel'

const baseTimer: WarmupSessionTimerData = {
  elapsed_seconds: 0,
  session_id: 'session-1',
  started_at: '2026-06-05T10:00:00Z',
  status: 'running',
  total_duration_seconds: 3600,
}

describe('WarmupSessionTimer', () => {
  test('formats elapsed under an hour against total duration', () => {
    expect(formatTimerText(28, 3600)).toBe('0:28 / 1:00:00')
  })

  test('running snapshot', () => {
    expect(
      renderTimer(
        { ...baseTimer, elapsed_seconds: 20, status: 'running' },
        new Date('2026-06-05T10:00:28Z'),
      ),
    ).toMatchSnapshot()
  })

  test('paused snapshot', () => {
    expect(renderTimer({ ...baseTimer, elapsed_seconds: 600, status: 'paused' })).toMatchSnapshot()
  })

  test('completed snapshot', () => {
    expect(
      renderTimer({ ...baseTimer, elapsed_seconds: 3600, status: 'completed' }),
    ).toMatchSnapshot()
  })
})

function renderTimer(timer: WarmupSessionTimerData, now?: Date): string {
  const queryClient = new QueryClient()
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <WarmupSessionTimer sessionId={timer.session_id} timer={timer} now={now} />
    </QueryClientProvider>,
  )
}
