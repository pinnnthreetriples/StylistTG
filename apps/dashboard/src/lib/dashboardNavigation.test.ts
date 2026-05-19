import { describe, expect, it } from 'vitest'

import { readCachedDashboardHydration } from '@/lib/dashboardNavigation'
import type { DashboardState } from '@/lib/dashboardCache'
import type { FormState } from '@/lib/dashboard'

const dashboard = {
  account: { account_id: 'account-1' },
  current_profile: {
    first_name: 'Ada',
    last_name: 'Lovelace',
    bio: 'math',
    username: 'ada',
    profile_photo_asset_id: 'photo-1',
  },
  editable_fields: {
    name: 'Ada Lovelace',
    bio: 'math',
    username: 'ada',
    profile_photo: 'photo-1',
  },
  profile_audio: null,
} as DashboardState

function storage(values: Record<string, string>) {
  return {
    getItem: (key: string) => values[key] ?? null,
  }
}

describe('dashboard navigation hydration', () => {
  it('hydrates editor state from dashboard cache for fast account navigation', () => {
    const result = readCachedDashboardHydration(
      storage({
        'stylisttg.dashboard.account-1': JSON.stringify(dashboard),
      }),
      'account-1',
    )

    expect(result?.dashboard.account.account_id).toBe('account-1')
    expect(result?.baselineForm).toMatchObject({ firstName: 'Ada', username: 'ada' })
    expect(result?.nextForm).toEqual(result?.baselineForm)
  })

  it('keeps a stored draft visible while backend refresh runs in background', () => {
    const draft: FormState = {
      firstName: 'Draft',
      lastName: 'Name',
      bio: 'draft bio',
      username: 'draft_user',
      profilePhotoAssetId: null,
      pinnedChannelRef: null,
      profileAudioAction: 'keep',
      profileAudioAssetId: null,
      stories: [],
    }
    const result = readCachedDashboardHydration(
      storage({
        'stylisttg.dashboard.account-1': JSON.stringify(dashboard),
        'stylisttg.dashboard.formDraft.account-1': JSON.stringify(draft),
      }),
      'account-1',
    )

    expect(result?.baselineForm).toMatchObject({ firstName: 'Ada', username: 'ada' })
    expect(result?.nextForm).toMatchObject({ firstName: 'Draft', username: 'draft_user' })
  })
})
