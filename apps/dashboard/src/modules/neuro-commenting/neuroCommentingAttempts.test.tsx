import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, test } from 'vitest'

import { AttemptsSection } from './components/AttemptsSection'
import type { NeuroAttempt } from './types'

const attempt: NeuroAttempt = {
  id: 'attempt-1',
  campaign_id: 'campaign-1',
  generated_comment_id: 'comment-1',
  account_id: 'account-1',
  target_id: 'target-1',
  observed_post_id: null,
  telegram_message_id: 'tg-1',
  status: 'failed',
  send_strategy: 'comment',
  error_code: 'RATE_LIMIT_DENIED',
  error_message: 'target comments_per_hour limit exceeded',
  flood_wait_seconds: null,
  reserved_limit_at: null,
  created_at: '2026-05-19T10:00:00Z',
  sent_at: null,
  failed_at: '2026-05-19T10:01:00Z',
  updated_at: '2026-05-19T10:01:00Z',
}

describe('NeuroCommenting attempts UI', () => {
  test('renders attempt statuses and identifiers', () => {
    const html = renderToStaticMarkup(<AttemptsSection attempts={[attempt]} />)

    expect(html).toContain('attempt-1')
    expect(html).toContain('failed')
    expect(html).toContain('comment-1')
    expect(html).toContain('RATE_LIMIT_DENIED')
  })
})
