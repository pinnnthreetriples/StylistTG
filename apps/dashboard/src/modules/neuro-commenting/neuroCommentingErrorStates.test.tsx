import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, test, vi } from 'vitest'

vi.mock('./hooks', () => ({
  useAddCampaignAccount: () => ({ isError: false, isPending: false, mutate: vi.fn() }),
  useNeuroCampaignAccounts: () => ({ data: undefined, isError: true, isLoading: false }),
  useRemoveCampaignAccount: () => ({ isError: false, isPending: false, mutate: vi.fn() }),
}))

import { AccountsSection } from './components/AccountsSection'

describe('neuro-commenting error states', () => {
  test('AccountsSection renders error state when query isError', () => {
    const html = renderToStaticMarkup(<AccountsSection campaignId="campaign-1" />)
    expect(html).toContain('Не удалось загрузить данные')
  })
})
