import { describe, expect, it } from 'vitest'

import { reconcileDashboardFormState } from '@/lib/dashboardReconciliation'
import type { FormState } from '@/lib/dashboard'

const serverForm: FormState = {
  firstName: 'Ada',
  lastName: 'Lovelace',
  bio: 'math',
  username: 'ada',
  profilePhotoAssetId: null,
  pinnedChannelRef: null,
  profileAudioAction: 'keep',
  profileAudioAssetId: null,
  stories: [],
}

describe('dashboard form reconciliation', () => {
  it('uses stored draft on initial dashboard hydration', () => {
    const storedDraft = { ...serverForm, firstName: 'Draft' }

    const result = reconcileDashboardFormState({
      currentBaseline: null,
      currentForm: serverForm,
      formInitialized: false,
      serverForm,
      storedDraft,
    })

    expect(result.nextForm).toMatchObject({ firstName: 'Draft' })
    expect(result.nextBaseline).toBe(serverForm)
    expect(result.draftToPersist).toMatchObject({ firstName: 'Draft' })
    expect(result.shouldClearDraft).toBe(false)
  })

  it('keeps dirty text draft during background refresh but syncs story drafts', () => {
    const currentForm = { ...serverForm, firstName: 'Dirty' }
    const nextStory: FormState['stories'][number] = {
      draftId: 'draft-1',
      clientId: 'draft-1',
      action: 'post_image' as const,
      assetId: 'asset-1',
      fileName: 'Story image',
      caption: '',
      privacyPreset: 'contacts',
      activePeriodSeconds: 86400,
      protectContent: false,
    }

    const result = reconcileDashboardFormState({
      currentBaseline: serverForm,
      currentForm,
      formInitialized: true,
      serverForm: { ...serverForm, stories: [nextStory] },
      storedDraft: null,
    })

    expect(result.nextForm).toMatchObject({ firstName: 'Dirty', stories: [nextStory] })
    expect(result.nextBaseline).toBeNull()
    expect(result.draftToPersist).toEqual(result.nextForm)
    expect(result.shouldClearDraft).toBe(false)
  })

  it('resets to server form and clears draft after explicit reset', () => {
    const currentForm = { ...serverForm, firstName: 'Dirty' }

    const result = reconcileDashboardFormState({
      currentBaseline: serverForm,
      currentForm,
      formInitialized: true,
      resetForm: true,
      serverForm,
      storedDraft: currentForm,
    })

    expect(result.nextForm).toBe(serverForm)
    expect(result.nextBaseline).toBe(serverForm)
    expect(result.draftToPersist).toBeNull()
    expect(result.shouldClearDraft).toBe(true)
  })
})
