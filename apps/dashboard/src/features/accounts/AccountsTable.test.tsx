import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, test } from 'vitest'

import { AccountsTable } from '@/features/accounts/AccountsTable'
import type { AccountListItem } from '@/lib/api'

const account: AccountListItem = {
  account_id: 'acc_1',
  display_name: 'Demo Account',
  username: 'demo',
  phone_number: '+10000000000',
  telegram_user_id: null,
  account_state: 'authorized',
  runtime_health: 'ready',
  is_execution_usable: true,
  is_test_dc: true,
  profile_photo_asset_id: null,
  updated_at: '2026-05-02T00:00:00Z',
}

describe('AccountsTable', () => {
  test('renders an account table with TanStack columns', () => {
    const html = renderToStaticMarkup(<AccountsTable accounts={[account]} />)

    expect(html).toContain('Demo Account')
    expect(html).toContain('Runtime')
  })
})
