import { afterEach, describe, expect, it, vi } from 'vitest'

import { getApiBaseUrl, getPollingIntervalMs, getRequestTimeoutMs } from '@/lib/config'
import { apiRequest, isApiError } from '@/lib/http'

describe('frontend config', () => {
  it('uses safe defaults for local development', () => {
    expect(getApiBaseUrl()).toBe('')
    expect(getPollingIntervalMs()).toBe(3000)
    expect(getRequestTimeoutMs()).toBe(15000)
  })
})

describe('apiRequest', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('returns parsed json for successful responses', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ ok: true }), {
          headers: { 'Content-Type': 'application/json' },
          status: 200,
        }),
      ),
    )

    await expect(apiRequest<{ ok: boolean }>('/api/test')).resolves.toEqual({ ok: true })
  })

  it('returns null for empty successful responses', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(null, {
          headers: { 'Content-Type': 'application/json' },
          status: 204,
        }),
      ),
    )

    await expect(apiRequest<void>('/api/test', { method: 'DELETE' })).resolves.toBeNull()
  })

  it('does not pass custom timeout option to fetch', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        headers: { 'Content-Type': 'application/json' },
        status: 200,
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await expect(apiRequest<{ ok: boolean }>('/api/test', { timeoutMs: 45000 })).resolves.toEqual({ ok: true })

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/test',
      expect.not.objectContaining({
        timeoutMs: expect.any(Number),
      }),
    )
  })

  it('throws backend api errors without losing their shape', async () => {
    const payload = {
      error_code: 'RUNTIME_UNUSABLE',
      error_class: 'runtime',
      message: 'runtime is not ready',
      details: null,
      field_errors: [],
      request_id: 'req-1',
    }
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify(payload), {
          headers: { 'Content-Type': 'application/json' },
          status: 400,
        }),
      ),
    )

    await expect(apiRequest('/api/test')).rejects.toEqual(payload)
  })

  it('throws a frontend network error when the backend response is not an api error', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response('service unavailable', {
          headers: { 'Content-Type': 'text/plain' },
          status: 503,
        }),
      ),
    )

    try {
      await apiRequest('/api/test')
      throw new Error('expected request to fail')
    } catch (error) {
      expect(isApiError(error)).toBe(true)
      expect(error).toMatchObject({
        error_code: 'NETWORK_ERROR',
        error_class: 'network',
        message: 'request failed with status 503',
        details: null,
        field_errors: [],
      })
    }
  })
})
