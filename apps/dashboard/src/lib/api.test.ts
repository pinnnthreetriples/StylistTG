import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  createStoryDraft,
  deleteStoryDraft,
  deleteStoryPost,
  deleteAccount,
  fetchAccounts,
  fetchStoryCapabilities,
  fetchStoryDrafts,
  fetchDashboard,
  storyDraftReadToPayload,
  updateStoryDraft,
  type StoryDraftRead,
} from '@/lib/api'

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    headers: { 'Content-Type': 'application/json' },
    status,
  })
}

function mockFetch(payload: unknown, status = 200) {
  const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(jsonResponse(payload, status)))
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

describe('story draft api contract', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('maps story draft reads into editable payloads', () => {
    const draft: StoryDraftRead = {
      id: 'draft-1',
      account_id: 'account-1',
      asset_id: 'asset-1',
      media_kind: 'video',
      caption: null,
      privacy_preset: 'contacts',
      active_period_seconds: 86400,
      protect_content: true,
      validation_status: 'ready',
      created_at: '2026-04-24T00:00:00Z',
      updated_at: '2026-04-24T00:00:00Z',
    }

    expect(storyDraftReadToPayload(draft)).toMatchObject({
      draftId: 'draft-1',
      clientId: 'draft-1',
      action: 'post_video',
      assetId: 'asset-1',
      caption: '',
      privacyPreset: 'contacts',
      activePeriodSeconds: 86400,
      protectContent: true,
    })
  })

  it('fetches story drafts by account id', async () => {
    const fetchMock = mockFetch([])

    await expect(fetchStoryDrafts('account-1')).resolves.toEqual([])

    expect(fetchMock).toHaveBeenCalledWith('/api/story-drafts', expect.objectContaining({
      headers: expect.objectContaining({ 'X-Account-Id': 'account-1' }),
      signal: expect.any(AbortSignal),
    }))
  })

  it('fetches story capabilities by account id', async () => {
    const payload = {
      account_id: 'account-1',
      stories_enabled: true,
      tdlib_live_publishing_enabled: false,
      can_prepare_image: true,
      can_prepare_video: true,
      allowed_active_period_seconds: [86400],
      allowed_privacy_presets: ['contacts', 'close_friends', 'public'],
      max_caption_length: 1024,
      ffprobe_available: false,
      ffmpeg_available: false,
      warnings: ['stories live TDLib publishing is disabled'],
    }
    const fetchMock = mockFetch(payload)

    await expect(fetchStoryCapabilities('account-1')).resolves.toEqual(payload)

    expect(fetchMock).toHaveBeenCalledWith('/api/story-capabilities', expect.objectContaining({
      headers: expect.objectContaining({ 'X-Account-Id': 'account-1' }),
      signal: expect.any(AbortSignal),
    }))
  })

  it('fetches dashboard through account header instead of account id in url', async () => {
    const fetchMock = mockFetch({ ok: true })

    await fetchDashboard('account-1')

    expect(fetchMock).toHaveBeenCalledWith('/api/dashboard/profile', expect.objectContaining({
      headers: expect.objectContaining({ 'X-Account-Id': 'account-1' }),
      signal: expect.any(AbortSignal),
    }))
  })

  it('fetches account summaries for the account list', async () => {
    const payload = [
      {
        account_id: 'account-1',
        display_name: 'Marina Manina',
        username: 'kkk4n44',
        phone_number: '+15550102000',
        telegram_user_id: '777000',
        account_state: 'execution_usable',
        runtime_health: 'ready',
        is_execution_usable: true,
        is_test_dc: false,
        updated_at: '2026-04-25T10:00:00Z',
      },
    ]
    const fetchMock = mockFetch(payload)

    await expect(fetchAccounts()).resolves.toEqual(payload)

    const [request] = fetchMock.mock.calls[0] as [Request]
    expect(request.url).toBe('http://localhost/api/accounts')
    expect(request.signal).toBeInstanceOf(AbortSignal)
  })

  it('deletes an account by id', async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(new Response(null, { status: 204 })))
    vi.stubGlobal('fetch', fetchMock)

    await expect(deleteAccount('account-1')).resolves.toBeUndefined()

    expect(fetchMock).toHaveBeenCalledWith('/api/accounts/account-1', expect.objectContaining({
      method: 'DELETE',
      signal: expect.any(AbortSignal),
    }))
  })

  it('creates story drafts with backend snake_case fields', async () => {
    const fetchMock = mockFetch({ id: 'draft-1' }, 201)

    await createStoryDraft(
      'account-1',
      {
        assetId: 'asset-1',
        caption: 'Caption',
        privacyPreset: 'close_friends',
        activePeriodSeconds: 86400,
        protectContent: true,
      },
      'image',
    )

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(fetchMock.mock.calls[0][0]).toBe('/api/story-drafts')
    expect(init.method).toBe('POST')
    expect(JSON.parse(init.body as string)).toEqual({
      account_id: 'account-1',
      asset_id: 'asset-1',
      media_kind: 'image',
      caption: 'Caption',
      privacy_preset: 'close_friends',
      active_period_seconds: 86400,
      protect_content: true,
    })
  })

  it('patches and deletes story drafts by draft id', async () => {
    const fetchMock = mockFetch({ id: 'draft-1' })

    await updateStoryDraft('draft-1', { caption: 'Next', protectContent: false })
    await deleteStoryDraft('draft-1')

    const [, patchInit] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(fetchMock.mock.calls[0][0]).toBe('/api/story-drafts/draft-1')
    expect(patchInit.method).toBe('PATCH')
    expect(JSON.parse(patchInit.body as string)).toEqual({
      caption: 'Next',
      protect_content: false,
    })
    expect(fetchMock.mock.calls[1][0]).toBe('/api/story-drafts/draft-1')
    expect((fetchMock.mock.calls[1][1] as RequestInit).method).toBe('DELETE')
  })

  it('deletes live story posts by post id and account header', async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(new Response(null, { status: 204 })))
    vi.stubGlobal('fetch', fetchMock)

    await expect(deleteStoryPost('account-1', 'post-1')).resolves.toBeUndefined()

    expect(fetchMock).toHaveBeenCalledWith('/api/story-posts/post-1', expect.objectContaining({
      method: 'DELETE',
      headers: expect.objectContaining({ 'X-Account-Id': 'account-1' }),
      signal: expect.any(AbortSignal),
    }))
  })

  it('treats missing story draft deletes as already deleted', async () => {
    mockFetch(
      {
        error_code: 'STORY_DRAFT_NOT_FOUND',
        error_class: 'not_found',
        message: 'story draft not found',
        details: null,
        field_errors: [],
        request_id: 'request-1',
      },
      404,
    )

    await expect(deleteStoryDraft('draft-1')).resolves.toBeUndefined()
  })
})
