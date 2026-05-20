import { describe, expect, it } from 'vitest'

import {
  accountMatchesAdvancedFilter,
  accountMatchesFilter,
  accountMatchesSearch,
  accountStatus,
  accountStats,
  maskPhone,
  type AccountAdvancedFilter,
  type AccountFilter,
} from '@/lib/accounts'
import type { AccountListItem } from '@/lib/api'
import type { AccountSafetySummary } from '@/lib/accountSafety'

function account(overrides: Partial<AccountListItem>): AccountListItem {
  return {
    account_id: 'account-1',
    display_name: 'Marina Manina',
    username: 'kkk4n44',
    phone_number: '+573181581884',
    telegram_user_id: '8612542342',
    origin: 'imported',
    account_state: 'execution_usable',
    runtime_health: 'ready',
    is_execution_usable: true,
    is_test_dc: false,
    profile_photo_asset_id: null,
    updated_at: '2026-04-25T10:00:00Z',
    ...overrides,
  }
}

function safety(overrides: Partial<AccountSafetySummary>): AccountSafetySummary {
  return {
    account_id: 'account-1',
    health_status: 'ready',
    overall_risk_level: 'low',
    validity_status: 'valid',
    capability_summary: {},
    cooldown_summary: [],
    top_reasons: [],
    last_checked_at: '2026-04-30T00:00:00Z',
    source: 'db_snapshot',
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

  it('filters accounts by safety readiness for advanced account management', () => {
    const base = account({ account_id: '1' })
    const paused = safety({
      cooldown_summary: [
        {
          id: 'cooldown-1',
          account_id: '1',
          operation: 'username',
          level: 'blocked',
          reason_code: 'recent_flood_wait',
          started_at: '2026-04-30T00:00:00Z',
          retry_after_at: '2026-04-30T00:10:00Z',
          source: 'job_step_result',
          source_job_id: null,
          source_step_id: null,
        },
      ],
    })

    expect(accountMatchesAdvancedFilter(base, safety({ health_status: 'ready' }), 'safety_ready')).toBe(true)
    expect(accountMatchesAdvancedFilter(base, safety({ health_status: 'blocked' }), 'needs_login')).toBe(true)
    expect(accountMatchesAdvancedFilter(base, paused, 'paused')).toBe(true)
    expect(accountMatchesAdvancedFilter(base, safety({ health_status: 'attention' }), 'limited')).toBe(true)
    expect(accountMatchesAdvancedFilter(base, null, 'unchecked')).toBe(true)

    const filters: AccountAdvancedFilter[] = ['all', 'safety_ready', 'needs_login', 'paused', 'limited', 'unchecked']
    expect(filters.every((filter) => typeof filter === 'string')).toBe(true)
  })

  it('masks phone numbers without hiding short test numbers completely', () => {
    expect(maskPhone('+573181581884')).toBe('+573 *** **-84')
    expect(maskPhone('+9996611234')).toBe('+999 *** **-34')
  })
})
