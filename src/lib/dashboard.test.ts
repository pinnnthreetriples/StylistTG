import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  areDashboardFormStatesEqual,
  buildDashboardFormState,
  buildChangeItems,
  clearProfilePhotoDraft,
  buildJobMetrics,
  buildRuntimeBanner,
  clearStoredDashboardFormDraft,
  formatAccountStateLabel,
  formatJobActivityText,
  formatRelativeTimestamp,
  groupRealExecutionChanges,
  isSupportedProfileAudioFile,
  appKnownMediaSyncNote,
  persistStoredDashboardFormDraft,
  readStoredDashboardFormDraft,
  reconcileStoredDashboardFormDraft,
  resolvePhotoPreview,
  resolveProfilePhotoPreviewUrl,
  resolveDashboardIdentity,
  resolveAccountId,
  shouldConfirmRealTelegramExecution,
  syncStateLabels,
  splitDisplayName,
} from '@/lib/dashboard'

afterEach(() => {
  vi.useRealTimers()
})

describe('resolveAccountId', () => {
  it('prefers query parameter over env fallback', () => {
    expect(resolveAccountId('?account_id=query-id', 'env-id')).toBe('query-id')
  })

  it('returns env fallback when query parameter is absent', () => {
    expect(resolveAccountId('', 'env-id')).toBe('env-id')
  })
})

describe('splitDisplayName', () => {
  it('splits a profile display name into first and last name', () => {
    expect(splitDisplayName('Алексей Петров')).toEqual({
      firstName: 'Алексей',
      lastName: 'Петров',
    })
  })
})

describe('buildChangeItems', () => {
  it('marks only changed operations and keeps plan order', () => {
    const items = buildChangeItems(
      {
        first_name: 'Алексей',
        last_name: 'Петров',
        bio: 'Старое описание',
        username: 'alexey_petrov',
        profile_photo_asset_id: 'asset-current',
        profile_audio_asset_id: null,
      },
      {
        firstName: 'Алексей',
        lastName: 'П.',
        bio: 'Новое описание',
        username: 'alexey_petrov',
        profilePhotoAssetId: 'asset-current',
        profileAudioAction: 'add',
        profileAudioAssetId: 'audio-new',
        stories: [],
      },
    )

    expect(items.map((item) => item.operation)).toEqual([
      'set_name',
      'set_bio',
      'set_username',
      'set_profile_photo',
      'add_profile_audio',
    ])
    expect(items.filter((item) => item.changed).map((item) => item.operation)).toEqual([
      'set_name',
      'set_bio',
      'add_profile_audio',
    ])
  })
})

describe('real Telegram execution confirmation helpers', () => {
  const changedItems = [
    { operation: 'set_name', changed: true, value: 'Old -> New' },
    { operation: 'add_profile_audio', changed: true, value: 'Музыка будет обновлена' },
    { operation: 'post_story_video', changed: true, value: 'story.mp4' },
  ] satisfies Parameters<typeof groupRealExecutionChanges>[0]

  it('groups planned changes by product module', () => {
    expect(groupRealExecutionChanges(changedItems)).toEqual({
      profile: [changedItems[0]],
      music: [changedItems[1]],
      stories: [changedItems[2]],
    })
  })

  it('requires confirmation for profile or music changes when TDLib execution is enabled', () => {
    expect(
      shouldConfirmRealTelegramExecution({ real_execution_enabled: true, stories_live_execution_enabled: false }, [
        changedItems[0],
      ]),
    ).toBe(true)
    expect(
      shouldConfirmRealTelegramExecution({ real_execution_enabled: true, stories_live_execution_enabled: false }, [
        changedItems[1],
      ]),
    ).toBe(true)
  })

  it('requires confirmation for stories only when live story publishing is enabled', () => {
    expect(
      shouldConfirmRealTelegramExecution({ real_execution_enabled: true, stories_live_execution_enabled: false }, [
        changedItems[2],
      ]),
    ).toBe(false)
    expect(
      shouldConfirmRealTelegramExecution({ real_execution_enabled: true, stories_live_execution_enabled: true }, [
        changedItems[2],
      ]),
    ).toBe(true)
  })

  it('does not require confirmation for mock execution', () => {
    expect(
      shouldConfirmRealTelegramExecution({ real_execution_enabled: false, stories_live_execution_enabled: false }, changedItems),
    ).toBe(false)
  })
})

describe('isSupportedProfileAudioFile', () => {
  it('accepts MP3 and M4A by mime type or extension', () => {
    expect(isSupportedProfileAudioFile({ name: 'track.bin', type: 'audio/mpeg' })).toBe(true)
    expect(isSupportedProfileAudioFile({ name: 'voice.m4a', type: '' })).toBe(true)
  })

  it('rejects unsupported profile audio formats before upload', () => {
    expect(isSupportedProfileAudioFile({ name: 'voice.ogg', type: 'audio/ogg' })).toBe(false)
    expect(isSupportedProfileAudioFile({ name: 'voice.wav', type: 'audio/wav' })).toBe(false)
  })
})

describe('sync clarity labels', () => {
  it('keeps stable product wording for Telegram, app-known, and draft states', () => {
    expect(syncStateLabels).toEqual({
      telegramCurrent: 'Текущее в Telegram',
      appKnown: 'Известно приложению',
      draft: 'Черновик изменений',
    })
    expect(appKnownMediaSyncNote).toContain('Фото, музыка и истории')
    expect(appKnownMediaSyncNote).toContain('StylistTG')
  })
})

describe('buildRuntimeBanner', () => {
  it('builds a runtime error banner from api errors', () => {
    expect(
      buildRuntimeBanner({
        apiError: {
          error_code: 'RUNTIME_UNUSABLE',
          error_class: 'runtime',
          message: 'account is not execution_usable',
          details: null,
          field_errors: [],
          request_id: 'req-1',
        },
      }),
    ).toEqual({
      title: 'Аккаунт пока не готов к работе',
      description: 'account is not execution_usable',
      accent: 'error',
    })
  })
})

describe('formatAccountStateLabel', () => {
  it('maps execution state to a user-facing russian label', () => {
    expect(formatAccountStateLabel('execution_usable')).toBe('Авторизован')
    expect(formatAccountStateLabel('reauth_required')).toBe('Нужен вход')
  })
})

describe('buildJobMetrics', () => {
  it('excludes dedup-blocked jobs from headline counters', () => {
    expect(
      buildJobMetrics([
        { job_state: 'completed' },
        { job_state: 'queued' },
        { job_state: 'manual_intervention_needed' },
        { job_state: 'dedup_blocked' },
      ]),
    ).toEqual({
      total: 3,
      success: 1,
      issues: 1,
    })
  })
})

describe('resolveDashboardIdentity', () => {
  it('prefers current_profile values over fallback account fields', () => {
    expect(
      resolveDashboardIdentity(
        {
          first_name: 'King',
          last_name: 'Blackburn',
          bio: 'Live from Telegram',
          username: 'kingblackburn',
          profile_photo_asset_id: null,
          profile_audio_asset_id: null,
        },
        {
          display_name: 'Stale Local Name',
          username: 'stale_username',
        },
      ),
    ).toEqual({
      displayName: 'King Blackburn',
      username: 'kingblackburn',
    })
  })
})

describe('buildDashboardFormState', () => {
  it('hydrates editable form fields from current_profile text fields', () => {
    expect(
      buildDashboardFormState({
        current_profile: {
          first_name: 'King',
          last_name: 'Blackburn',
          bio: 'Live from Telegram',
          username: 'kingblackburn',
          profile_photo_asset_id: null,
        },
        editable_fields: {
          name: 'Stale Local Name',
          bio: 'Stale Local Bio',
          username: 'stale_username',
          profile_photo: 'asset-1',
        },
      }),
    ).toEqual({
      firstName: 'King',
      lastName: 'Blackburn',
      bio: 'Live from Telegram',
      username: 'kingblackburn',
      profilePhotoAssetId: 'asset-1',
      profileAudioAction: 'keep',
      profileAudioAssetId: null,
      stories: [],
    })
  })
})

describe('dashboard form draft storage', () => {
  it('round-trips a changed form draft for one account', () => {
    const storage = new Map<string, string>()
    const fakeStorage = {
      getItem: (key: string) => storage.get(key) ?? null,
      setItem: (key: string, value: string) => storage.set(key, value),
      removeItem: (key: string) => storage.delete(key),
    }
    const draft = {
      firstName: 'Draft',
      lastName: 'User',
      bio: 'Unsaved bio',
      username: 'draft_user',
      profilePhotoAssetId: 'asset-draft',
      profileAudioAction: 'add',
      profileAudioAssetId: 'audio-draft',
      stories: [],
    } satisfies Parameters<typeof persistStoredDashboardFormDraft>[2]

    persistStoredDashboardFormDraft(fakeStorage, 'account-1', draft)

    expect(readStoredDashboardFormDraft(fakeStorage, 'account-1')).toEqual(draft)
    expect(readStoredDashboardFormDraft(fakeStorage, 'account-2')).toBeNull()

    clearStoredDashboardFormDraft(fakeStorage, 'account-1')
    expect(readStoredDashboardFormDraft(fakeStorage, 'account-1')).toBeNull()
  })
})

describe('reconcileStoredDashboardFormDraft', () => {
  it('drops stored story drafts that no longer exist on the server', () => {
    const storedDraft = {
      firstName: 'Draft',
      lastName: '',
      bio: '',
      username: '',
      profilePhotoAssetId: null,
      profileAudioAction: 'keep' as const,
      profileAudioAssetId: null,
      stories: [
        {
          draftId: 'stale-draft',
          clientId: 'stale-draft',
          action: 'post_image' as const,
          assetId: 'asset-1',
          fileName: 'Story image',
          caption: '',
          privacyPreset: 'contacts' as const,
          activePeriodSeconds: 86400 as const,
          protectContent: false,
        },
      ],
    }
    const serverForm = { ...storedDraft, stories: [] }

    expect(reconcileStoredDashboardFormDraft(storedDraft, serverForm).stories).toEqual([])
  })
})

describe('areDashboardFormStatesEqual', () => {
  it('detects whether a dashboard form differs from its hydrated baseline', () => {
    const baseline = {
      firstName: 'King',
      lastName: 'Blackburn',
      bio: 'Live from Telegram',
      username: 'kingblackburn',
      profilePhotoAssetId: null,
      profileAudioAction: 'keep',
      profileAudioAssetId: null,
      stories: [],
    } satisfies Parameters<typeof areDashboardFormStatesEqual>[0]

    expect(areDashboardFormStatesEqual(baseline, { ...baseline })).toBe(true)
    expect(areDashboardFormStatesEqual(baseline, { ...baseline, bio: 'Draft bio' })).toBe(false)
    expect(areDashboardFormStatesEqual(baseline, { ...baseline, profileAudioAction: 'remove' })).toBe(false)
  })
})

describe('resolvePhotoPreview', () => {
  it('marks uploaded photo preview as available when local object url exists', () => {
    expect(resolvePhotoPreview('blob:http://127.0.0.1/mock-photo')).toEqual({
      imageUrl: 'blob:http://127.0.0.1/mock-photo',
      hasPreview: true,
    })
  })

  it('returns empty preview state when no local image exists', () => {
    expect(resolvePhotoPreview(null)).toEqual({
      imageUrl: null,
      hasPreview: false,
    })
  })
})

describe('resolveProfilePhotoPreviewUrl', () => {
  it('prefers the local object url while the selected file is still in memory', () => {
    expect(
      resolveProfilePhotoPreviewUrl('blob:http://127.0.0.1/mock-photo', 'asset-1', (assetId) => `/assets/${assetId}`),
    ).toBe('blob:http://127.0.0.1/mock-photo')
  })

  it('falls back to asset content url after reload when only the draft asset id remains', () => {
    expect(resolveProfilePhotoPreviewUrl(null, 'asset-draft', (assetId) => `/api/assets/${assetId}/content`)).toBe(
      '/api/assets/asset-draft/content',
    )
  })
})

describe('clearProfilePhotoDraft', () => {
  it('clears selected photo asset from the draft form', () => {
    expect(
      clearProfilePhotoDraft({
        firstName: 'King',
        lastName: 'Blackburn',
        bio: 'Live',
        username: 'king',
        profilePhotoAssetId: 'asset-draft',
        profileAudioAction: 'keep',
        profileAudioAssetId: null,
        stories: [],
      }),
    ).toEqual({
      firstName: 'King',
      lastName: 'Blackburn',
      bio: 'Live',
      username: 'king',
      profilePhotoAssetId: null,
      profileAudioAction: 'keep',
      profileAudioAssetId: null,
      stories: [],
    })
  })
})

describe('formatJobActivityText', () => {
  it('returns explicit text for queued and deduplicated jobs', () => {
    expect(formatJobActivityText({ job_state: 'queued', finished_at: null, message: null })).toBe(
      'Задача в очереди',
    )
    expect(
      formatJobActivityText({
        job_state: 'dedup_blocked',
        finished_at: null,
        message: 'job deduplicated by active execution intent',
      }),
    ).toBe('Такая задача уже стоит в очереди')
  })
})

describe('formatRelativeTimestamp', () => {
  it('treats API timestamps without timezone as UTC', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-04-24T19:01:45Z'))

    expect(formatRelativeTimestamp('2026-04-24T19:00:45.887088')).toBe('1 мин назад')
  })
})
