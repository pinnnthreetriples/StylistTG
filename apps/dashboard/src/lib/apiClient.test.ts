import { afterEach, describe, expect, test, vi } from 'vitest'

import { dashboardApiClient, resetApiAccessTokenProvider, setApiAccessTokenProvider } from '@/lib/apiClient'

describe('dashboard API client', () => {
  afterEach(() => {
    resetApiAccessTokenProvider()
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  test('injects the current Supabase access token into API requests', async () => {
    const calls: RequestInit[] = []
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      calls.push(init ?? {})
      return new Response(JSON.stringify({ ok: true }), {
        headers: { 'Content-Type': 'application/json' },
      })
    })
    vi.stubGlobal('fetch', fetchMock)
    setApiAccessTokenProvider(() => 'jwt-1')

    await dashboardApiClient.request('/api/me')

    expect(new Headers(calls[0].headers).get('Authorization')).toBe('Bearer jwt-1')
  })
})
