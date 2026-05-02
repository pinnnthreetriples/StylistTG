import { describe, expect, test } from 'vitest'

import { createApiClient, createStylistTgClient, fetchRuntimeDiagnostics, normalizeClientError, resolveApiBaseUrl } from './index'
import type { paths } from './generated/schema'

describe('@stylisttg/api-client', () => {
  test('generated OpenAPI types can be imported', () => {
    const pathKeys: keyof paths | null = null

    expect(pathKeys).toBeNull()
  })

  test('creates a client with a normalized base URL', () => {
    const client = createStylistTgClient({ baseUrl: 'http://localhost:8000/' })

    expect(client).toBeTruthy()
    expect(client.baseUrl).toBe('http://localhost:8000')
    expect(resolveApiBaseUrl('http://localhost:8000/')).toBe('http://localhost:8000')
  })

  test('adds authorization only when a token exists', async () => {
    const calls: RequestInit[] = []
    const fetchMock = async (_input: RequestInfo | URL, init?: RequestInit) => {
      calls.push(init ?? {})
      return new Response(JSON.stringify({ ok: true }), { headers: { 'Content-Type': 'application/json' } })
    }
    const client = createApiClient({
      baseUrl: 'http://localhost:8000',
      fetch: fetchMock as typeof fetch,
      getAccessToken: () => 'token-1',
    })

    await client.request('/health')

    expect(new Headers(calls[0]?.headers).get('Authorization')).toBe('Bearer token-1')
  })

  test('health endpoint wrapper is typed through generated OpenAPI paths', async () => {
    const client = createApiClient({
      baseUrl: 'http://localhost:8000',
      fetch: (async () =>
        new Response(JSON.stringify({ database: 'ok', redis: 'ok', tdlib: 'not_configured' }), {
          headers: { 'Content-Type': 'application/json' },
        })) as typeof fetch,
    })

    await expect(fetchRuntimeDiagnostics(client)).resolves.toEqual({
      database: 'ok',
      redis: 'ok',
      tdlib: 'not_configured',
    })
  })

  test('normalizes backend and network errors', () => {
    expect(normalizeClientError({ error_code: 'NOPE', message: 'failed', details: { safe: true } }, 503)).toEqual({
      status: 503,
      code: 'NOPE',
      message: 'failed',
      details: { safe: true },
    })
  })

  test('does not hardcode the staging URL', () => {
    expect(resolveApiBaseUrl(undefined)).toBe('')
    expect(String(createStylistTgClient)).not.toContain('code.run')
  })
})
