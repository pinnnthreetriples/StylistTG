import { describe, expect, it } from 'vitest'

import {
  clearDashboardCache,
  persistDashboardCache,
  readStoredDashboardCache,
  type DashboardState,
} from '@/lib/dashboardCache'

function dashboard(accountId: string): DashboardState {
  return {
    account: {
      account_id: accountId,
      display_name: 'Test User',
      username: 'test',
      phone_number: '+10000000000',
      telegram_user_id: null,
      account_state: 'execution_usable',
      runtime_health: 'ready',
      reauth_required: false,
      is_execution_usable: true,
    },
    current_profile: {
      first_name: 'Test',
      last_name: 'User',
      bio: '',
      username: 'test',
      profile_photo_asset_id: null,
    },
    profile_audio: null,
    story_posts: [],
    editable_fields: {
      name: 'Test User',
      bio: '',
      username: 'test',
      profile_photo: null,
    },
    pipeline: {
      latest_job_id: null,
      latest_job_state: null,
      latest_job: null,
      latest_job_finished_at: null,
      has_active_job: false,
      unsaved_changes_supported: true,
    },
    diagnostics: {
      last_error_code: null,
      last_error_class: null,
      authorized_last_confirmed_at: null,
      real_execution_enabled: false,
      stories_live_execution_enabled: false,
    },
  }
}

describe('dashboard cache', () => {
  it('round-trips dashboard state by account id', () => {
    const storage = new Map<string, string>()
    const fakeStorage = {
      getItem: (key: string) => storage.get(key) ?? null,
      setItem: (key: string, value: string) => storage.set(key, value),
      removeItem: (key: string) => storage.delete(key),
    }

    persistDashboardCache(fakeStorage, 'account-1', dashboard('account-1'))

    expect(readStoredDashboardCache(fakeStorage, 'account-1')?.account.account_id).toBe('account-1')
    expect(readStoredDashboardCache(fakeStorage, 'account-2')).toBeNull()

    clearDashboardCache(fakeStorage, 'account-1')
    expect(readStoredDashboardCache(fakeStorage, 'account-1')).toBeNull()
  })

  it('ignores malformed cache payloads', () => {
    const fakeStorage = {
      getItem: () => '{not-json',
    }

    expect(readStoredDashboardCache(fakeStorage, 'account-1')).toBeNull()
  })
})
