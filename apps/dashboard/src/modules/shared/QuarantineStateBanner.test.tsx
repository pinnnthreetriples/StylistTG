import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { QuarantineStateBanner } from './QuarantineStateBanner'

const activeQuarantine = {
  id: 'q-1',
  workspace_id: 'workspace-1',
  account_id: 'account-1',
  reason: 'flood_wait',
  started_at: '2026-05-20T08:00:00Z',
  until: '2026-05-21T08:00:00Z',
  released_at: null,
  released_by_user_id: null,
  metadata_json: {},
} as const

describe('QuarantineStateBanner', () => {
  it('renders active quarantine banner', () => {
    const html = renderToStaticMarkup(
      <QuarantineStateBanner accountId="account-1" initialQuarantine={activeQuarantine} />,
    )

    expect(html).toContain('В карантине до')
    expect(html).toContain('flood_wait')
  })

  it('is hidden when there is no quarantine', () => {
    const html = renderToStaticMarkup(
      <QuarantineStateBanner accountId="account-1" initialQuarantine={null} />,
    )

    expect(html).toBe('')
  })
})
