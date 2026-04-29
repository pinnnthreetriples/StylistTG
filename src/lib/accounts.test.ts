import { describe, expect, it } from 'vitest'

import {
  accountMatchesFilter,
  accountMatchesSearch,
  accountStatus,
  accountStats,
  maskPhone,
  type AccountFilter,
} from '@/lib/accounts'
import type { AccountListItem } from '@/lib/api'

function account(overrides: Partial<AccountListItem>): AccountListItem {
  return {
    account_id: 'account-1',
    display_name: 'Marina Manina',
    username: 'kkk4n44',
    phone_number: '+573181581884',
    telegram_user_id: '8612542342',
    account_state: 'execution_usable',
    runtime_health: 'ready',
    is_execution_usable: true,
    is_test_dc: false,
    profile_photo_asset_id: null,
    updated_at: '2026-04-25T10:00:00Z',
    ...overrides,
  }
}

describe('account list helpers', () => {
  it('derives account statuses from account state and runtime health', () => {
    expect(accountStatus(account({ is_execution_usable: true })).kind).toBe('authorized')
    expect(accountStatus(account({ account_state: 'authorized_ready', is_execution_usable: false })).kind).toBe('authorized')
    expect(accountStatus(account({ account_state: 'awaiting_code', is_execution_usable: false })).kind).toBe('waiting')
    expect(accountStatus(account({ account_state: 'runtime_broken', runtime_health: 'timeout', is_execution_usable: false })).kind).toBe('error')
  })

  it('counts total, authorized, waiting, and errored accounts', () => {
    const stats = accountStats([
      account({ account_id: '1', is_execution_usable: true }),
      account({ account_id: '2', account_state: 'awaiting_code', is_execution_usable: false }),
      account({ account_id: '3', account_state: 'runtime_broken', runtime_health: 'timeout', is_execution_usable: false }),
    ])

    expect(stats).toEqual({ total: 3, authorized: 1, waiting: 1, error: 1 })
  })

  it('filters accounts by status and searches by name, username, or phone', () => {
    const marina = account({ account_id: '1', display_name: 'Marina Manina', username: 'kkk4n44' })
    const waiting = account({ account_id: '2', display_name: 'Test User', account_state: 'awaiting_code', is_execution_usable: false })

    expect(accountMatchesFilter(waiting, 'waiting')).toBe(true)
    expect(accountMatchesFilter(marina, 'waiting')).toBe(false)
    expect(accountMatchesSearch(marina, 'manina')).toBe(true)
    expect(accountMatchesSearch(marina, 'kkk4')).toBe(true)
    expect(accountMatchesSearch(marina, '999')).toBe(false)

    const filters: AccountFilter[] = ['all', 'authorized', 'waiting', 'error']
    expect(filters.every((filter) => typeof filter === 'string')).toBe(true)
  })

  it('masks phone numbers without hiding short test numbers completely', () => {
    expect(maskPhone('+573181581884')).toBe('+573 *** **-84')
    expect(maskPhone('+9996611234')).toBe('+999 *** **-34')
  })
})
