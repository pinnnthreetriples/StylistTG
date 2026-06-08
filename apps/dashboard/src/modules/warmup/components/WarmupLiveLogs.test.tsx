import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, test, vi } from 'vitest'

import type { WarmupLiveEventPage } from '../types'
import { WarmupLiveLogs } from './WarmupLiveLogs'

vi.mock('../api', () => ({
  buildWarmupEventStreamUrl: vi.fn(async () => '/api/warmup-events/stream'),
  fetchWarmupLiveEvents: vi.fn(),
}))

const page: WarmupLiveEventPage = {
  accounts: [
    { account_id: 'acc-1', account_label: '+15550101000', phone_id: '+15550101000' },
    { account_id: 'acc-2', account_label: '+15550101001', phone_id: '+15550101001' },
  ],
  items: [
    {
      account_id: 'acc-1',
      account_label: '+15550101000',
      created_at: '2026-06-05T09:00:00Z',
      event_id: 'evt-1',
      event_type: 'micro_session_window_opened',
      id: 'evt-1',
      message: 'micro_session_window_opened',
      occurred_at: '2026-06-05T09:00:00Z',
      payload: {},
      phone_id: '+15550101000',
      session_id: 'sess-1',
      severity: 'info',
    },
    {
      account_id: 'acc-1',
      account_label: '+15550101000',
      created_at: '2026-06-05T09:01:00Z',
      event_id: 'evt-plan',
      event_type: 'session_plan_announced',
      id: 'evt-plan',
      message: 'session_plan_announced',
      occurred_at: '2026-06-05T09:01:00Z',
      payload: {
        account_age_days: 8,
        action_types: ['feed_read', 'view_dialogs', 'channel_browse'],
        avg_interval_minutes: 11,
        first_action_delay_seconds: 24,
        planned_actions_count: 3,
        session_duration_minutes: 33,
        stage: 'warming',
      },
      phone_id: '+15550101000',
      session_id: 'sess-1',
      severity: 'info',
    },
    {
      account_id: 'acc-1',
      account_label: '+15550101000',
      created_at: '2026-06-05T09:02:00Z',
      event_id: 'evt-2',
      event_type: 'session_action_executed',
      id: 'evt-2',
      message: 'session_action_executed: feed_read',
      occurred_at: '2026-06-05T09:02:00Z',
      payload: { action_type: 'feed_read' },
      phone_id: '+15550101000',
      session_id: 'sess-1',
      severity: 'success',
    },
  ],
  limit: 200,
  next_cursor: 'evt-2',
  total: 3,
}

describe('WarmupLiveLogs', () => {
  test('renders severity counters, account filter, search, and live log rows', () => {
    const queryClient = new QueryClient()

    const html = renderToStaticMarkup(
      <QueryClientProvider client={queryClient}>
        <WarmupLiveLogs eventsPage={page} />
      </QueryClientProvider>,
    )

    expect(html).toContain('Live-логи')
    expect(html).toContain('Все 3')
    expect(html).toContain('Инфо 2')
    expect(html).toContain('Успех 1')
    expect(html).toContain('Все аккаунты')
    expect(html).toContain('Поиск')
    expect(html).toContain('+15550101000')
    expect(html).toContain('Окно микро-сессии открыто')
    expect(html).toContain('План на сессию')
    expect(html).toContain('feed_read, view_dialogs, channel_browse')
    expect(html).toContain('Действие выполнено')
  })
})
