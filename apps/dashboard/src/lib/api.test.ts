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

function requestDetails(call: unknown[]) {
  const input = call[0] as RequestInfo | URL
  const init = (call[1] ?? {}) as RequestInit
  if (input instanceof Request) {
    return {
      url: new URL(input.url).pathname,
      method: input.method,
      headers: input.headers,
      body: input.body,
    }
  }
  return {
    url: String(input).replace(/^http:\/\/localhost/, ''),
    method: init.method ?? 'GET',
    headers: new Headers(init.headers),
    body: init.body,
  }
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

    const request = requestDetails(fetchMock.mock.calls[0])
    expect(request.url).toBe('/api/story-drafts')
    expect(request.headers.get('X-Account-Id')).toBe('account-1')
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

    const request = requestDetails(fetchMock.mock.calls[0])
    expect(request.url).toBe('/api/story-capabilities')
    expect(request.headers.get('X-Account-Id')).toBe('account-1')
  })

  it('fetches dashboard through account header instead of account id in url', async () => {
    const fetchMock = mockFetch({ ok: true })

    await fetchDashboard('account-1')

    const request = requestDetails(fetchMock.mock.calls[0])
    expect(request.url).toBe('/api/dashboard/profile')
    expect(request.headers.get('X-Account-Id')).toBe('account-1')
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

    const request = requestDetails(fetchMock.mock.calls[0])
    expect(request.url).toBe('/api/accounts/account-1')
    expect(request.method).toBe('DELETE')
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

    const request = requestDetails(fetchMock.mock.calls[0])
    expect(request.url).toBe('/api/story-drafts')
    expect(request.method).toBe('POST')
    expect(await new Response(request.body).json()).toEqual({
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

    const patchRequest = requestDetails(fetchMock.mock.calls[0])
    expect(patchRequest.url).toBe('/api/story-drafts/draft-1')
    expect(patchRequest.method).toBe('PATCH')
    expect(await new Response(patchRequest.body).json()).toEqual({
      caption: 'Next',
      protect_content: false,
    })
    const deleteRequest = requestDetails(fetchMock.mock.calls[1])
    expect(deleteRequest.url).toBe('/api/story-drafts/draft-1')
    expect(deleteRequest.method).toBe('DELETE')
  })

  it('deletes live story posts by post id and account header', async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(new Response(null, { status: 204 })))
    vi.stubGlobal('fetch', fetchMock)

    await expect(deleteStoryPost('account-1', 'post-1')).resolves.toBeUndefined()

    const request = requestDetails(fetchMock.mock.calls[0])
    expect(request.url).toBe('/api/story-posts/post-1')
    expect(request.method).toBe('DELETE')
    expect(request.headers.get('X-Account-Id')).toBe('account-1')
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
