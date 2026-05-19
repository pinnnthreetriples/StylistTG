import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, test } from 'vitest'

import { AnalyticsSection } from './components/AnalyticsSection'
import { ChannelHealthBadge } from './components/ChannelHealthBadge'
import type { NeuroAccountStats, NeuroCampaignStats, NeuroChannelStats } from './types'

const stats: NeuroCampaignStats = {
  campaign_id: 'campaign-1',
  posts_seen: 4,
  comments_generated: 3,
  comments_pending: 1,
  comments_edited: 0,
  comments_approved: 2,
  comments_rejected: 1,
  comments_sent: 2,
  comments_failed: 1,
  comments_skipped: 0,
  flood_wait_count: 1,
  success_rate: 2 / 3,
  approval_rate: 2 / 3,
  generation_rate: 0.75,
  last_observed_at: null,
  last_generated_at: null,
  last_sent_at: null,
}

const account: NeuroAccountStats = {
  account_id: 'account-1',
  comments_generated: 1,
  comments_sent: 2,
  comments_failed: 1,
  flood_wait_count: 1,
  success_rate: 2 / 3,
  last_success_at: null,
  last_failure_at: null,
  cooldown_until: '2026-05-19T12:00:00Z',
  status: 'cooldown',
}

const channel: NeuroChannelStats = {
  target_id: 'target-1',
  channel_ref: '@channel',
  title: 'Channel',
  posts_seen: 4,
  comments_generated: 3,
  comments_sent: 2,
  comments_failed: 1,
  flood_wait_count: 1,
  health_score: 0.84,
  success_rate: 2 / 3,
  last_success_at: '2026-05-19T11:00:00Z',
  last_failure_at: null,
  rule_status: 'whitelist',
}

describe('NeuroCommenting analytics UI', () => {
  test('renders stats cards and performance rows', () => {
    const html = renderToStaticMarkup(
      <AnalyticsSection stats={stats} accounts={[account]} channels={[channel]} />,
    )

    expect(html).toContain('Posts seen')
    expect(html).toContain('Generated')
    expect(html).toContain('67%')
    expect(html).toContain('account-1')
    expect(html).toContain('@channel')
    expect(html).toContain('whitelist')
  })

  test('formats channel health score as a percent tone', () => {
    const html = renderToStaticMarkup(<ChannelHealthBadge score={0.84} />)

    expect(html).toContain('84%')
    expect(html).toContain('data-tone="good"')
  })
})
