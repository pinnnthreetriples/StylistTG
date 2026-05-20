import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import {
  BoughtAccountOnboardingWizard,
  type BoughtOnboardingStatus,
} from './BoughtAccountOnboardingWizard'

const activeStatus: BoughtOnboardingStatus = {
  account_id: 'account-1',
  current_step: 'enable_2fa',
  completion_percent: 25,
  started_at: '2026-05-20T14:37:00Z',
  completed_at: null,
  details_json: {},
}

describe('BoughtAccountOnboardingWizard', () => {
  it('renders the current onboarding step', () => {
    const html = renderToStaticMarkup(
      <BoughtAccountOnboardingWizard accountId="account-1" initialStatus={activeStatus} />,
    )

    expect(html).toContain('Bought-account onboarding')
    expect(html).toContain('Enable 2FA')
    expect(html).toContain('25%')
  })

  it('renders a start action before onboarding exists', () => {
    const html = renderToStaticMarkup(
      <BoughtAccountOnboardingWizard accountId="account-1" initialStatus={null} />,
    )

    expect(html).toContain('Start onboarding')
  })
})
