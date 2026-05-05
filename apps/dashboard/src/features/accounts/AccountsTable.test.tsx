import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, test } from 'vitest'

import { AccountsTable } from '@/features/accounts/AccountsTable'
import { accountsViewStorageKey } from '@/features/accounts/accountsViewStorage'
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
    expect(html).toContain('Среда')
  })

  test('scopes saved accounts view keys by env workspace and user', () => {
    expect(accountsViewStorageKey({ appEnv: 'staging', workspaceId: 'workspace-1', userId: 'user-1' })).toBe(
      'stylisttg:staging:workspace-1:user-1:accounts:view',
    )
    expect(accountsViewStorageKey({ appEnv: 'local' })).toBe('stylisttg:local:local:local:accounts:view')
  })
})
