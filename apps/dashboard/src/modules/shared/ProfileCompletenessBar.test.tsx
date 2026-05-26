import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'

import { ProfileCompletenessBar } from './ProfileCompletenessBar'

vi.mock('@/lib/api', () => ({
  fetchProfileCompleteness: vi.fn(async () => ({
    account_id: 'account-1',
    score: 0.8,
    breakdown: {
      first_name: true,
      bio: true,
      profile_photo_asset_id: true,
      username: false,
      pinned_channel_ref: false,
    },
    missing_required: [],
    missing_recommended: ['username', 'pinned_channel_ref'],
    evaluated_at: '2026-05-20T08:00:00Z',
  })),
}))

describe('ProfileCompletenessBar', () => {
  it('renders percentage and green completeness bar', () => {
    const queryClient = new QueryClient()

    queryClient.setQueryData(['profileCompleteness', 'account-1'], {
      account_id: 'account-1',
      score: 0.8,
      breakdown: {
        first_name: true,
        bio: true,
        profile_photo_asset_id: true,
        username: false,
        pinned_channel_ref: false,
      },
      missing_required: [],
      missing_recommended: ['username', 'pinned_channel_ref'],
      evaluated_at: '2026-05-20T08:00:00Z',
    })

    const html = renderToStaticMarkup(
      <QueryClientProvider client={queryClient}>
        <ProfileCompletenessBar accountId="account-1" />
      </QueryClientProvider>,
    )

    expect(html).toContain('80%')
    expect(html).toContain('bg-muted')
  })
})
