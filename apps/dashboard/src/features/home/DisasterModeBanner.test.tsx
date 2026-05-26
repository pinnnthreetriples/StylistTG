import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import type { DisasterState } from '@/lib/api'
import { queryKeys } from '@/lib/queries'

import { DisasterModeBanner } from './DisasterModeBanner'

const disasterState: DisasterState = {
  workspace_id: '00000000-0000-4000-8000-000000000002',
  is_disaster: true,
  quarantined_count: 6,
  total_accounts: 10,
  quarantined_fraction: 0.6,
  threshold: 0.5,
  window_hours: 1,
  detected_at: '2026-05-22T12:00:00Z',
  sample_quarantined_account_ids: [
    '00000000-0000-4000-8000-000000000101',
    '00000000-0000-4000-8000-000000000102',
  ],
}

function renderBanner(state: DisasterState): string {
  const queryClient = new QueryClient()
  queryClient.setQueryData(queryKeys.dashboard.disasterState, state)

  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <DisasterModeBanner />
    </QueryClientProvider>,
  )
}

describe('DisasterModeBanner', () => {
  it('renders null when disaster mode is inactive', () => {
    const html = renderBanner({ ...disasterState, is_disaster: false })

    expect(html).toBe('')
  })

  it('renders the critical count banner when disaster mode is active', () => {
    const html = renderBanner(disasterState)

    expect(html).toContain('Disaster mode: 6/10 accounts in quarantine')
    expect(html).toContain('bg-destructive')
    expect(html).toContain('/accounts/00000000-0000-4000-8000-000000000101')
  })

  it('builds the support escalation mailto href', () => {
    const html = renderBanner(disasterState)

    expect(html).toContain(
      'mailto:support@?subject=Disaster%20mode%3A%206%2F10%20accounts%20in%20quarantine',
    )
  })
})
