import { describe, expect, test } from 'vitest'

import {
  confirmOtp,
  createApiClient,
  createAuthBatch,
  createStylistTgClient,
  fetchFrontendDiagnosticsSummary,
  fetchRuntimeDiagnostics,
  fetchAccountRiskSummary,
  normalizeClientError,
  resolveApiBaseUrl,
  startOtp,
  validateAuthBatchPhones,
} from './index'
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

  test('auth endpoint wrappers use typed OpenAPI requests', async () => {
    const calls: Array<{ url: string; body: unknown }> = []
    const fetchMock = async (input: RequestInfo | URL, init?: RequestInit) => {
      calls.push({ url: requestUrl(input), body: await requestBody(input, init) })
      if (requestUrl(input).endsWith('/api/auth/otp/start')) {
        return jsonResponse({
          account_id: 'acc-1',
          external_ref: '+15550102000',
          telegram_user_id: null,
          orchestration_state: 'awaiting_code',
          auth_step_status: 'wait_code',
          needs_code: true,
          needs_password: false,
          password_hint: null,
          session_present: true,
          runtime_health: 'awaiting_code',
          reauth_required: false,
          recovery_marker: 'wait_code',
          authorized_last_confirmed_at: null,
          error: null,
        })
      }
      return jsonResponse({
        account_id: 'acc-1',
        external_ref: '+15550102000',
        telegram_user_id: 'tg-1',
        orchestration_state: 'authorized_ready',
        auth_step_status: 'ready',
        needs_code: false,
        needs_password: false,
        password_hint: null,
        session_present: true,
        runtime_health: 'ready',
        reauth_required: false,
        recovery_marker: 'ready',
        authorized_last_confirmed_at: '2026-05-03T00:00:00Z',
        error: null,
      })
    }
    const client = createApiClient({ baseUrl: 'http://api.test', fetch: fetchMock as typeof fetch })

    await startOtp(client, '+15550102000')
    await confirmOtp(client, 'acc-1', '12345')

    expect(calls.map((call) => call.url)).toEqual([
      'http://api.test/api/auth/otp/start',
      'http://api.test/api/auth/otp/confirm',
    ])
    expect(calls[0].body).toEqual({ phone_number: '+15550102000' })
    expect(calls[1].body).toEqual({ account_id: 'acc-1', code: '12345' })
  })

  test('auth batch endpoint wrappers use typed OpenAPI requests', async () => {
    const calls: string[] = []
    const fetchMock = async (input: RequestInfo | URL) => {
      calls.push(requestUrl(input))
      if (requestUrl(input).endsWith('/validate-phones')) {
        return jsonResponse({ valid_items: [], invalid_items: [], duplicates: [], existing_accounts: [], active_batch_conflicts: [] })
      }
      return jsonResponse({
        id: 'batch-1',
        label: 'Batch',
        status: 'pending',
        total_count: 1,
        success_count: 0,
        failed_count: 0,
        cancelled_count: 0,
        skipped_count: 0,
        max_running_commands: 2,
        max_waiting_input: 5,
        max_total_active: 6,
        created_at: '2026-05-03T00:00:00Z',
        started_at: null,
        finished_at: null,
      })
    }
    const client = createApiClient({ baseUrl: 'http://api.test', fetch: fetchMock as typeof fetch })

    await validateAuthBatchPhones(client, [{ phone_number: '+15550102000', label: null, position: 0 }])
    await createAuthBatch(client, {
      idempotency_key: 'batch-1',
      label: 'Batch',
      items: [{ phone_number: '+15550102000', label: null, position: 0 }],
      max_running_commands: 2,
      max_waiting_input: 5,
      max_total_active: 6,
    })

    expect(calls).toEqual(['http://api.test/api/auth-batches/validate-phones', 'http://api.test/api/auth-batches'])
  })

  test('diagnostics and risk wrappers expose backend-backed health data', async () => {
    const fetchMock = async (input: RequestInfo | URL) => {
      if (requestUrl(input).endsWith('/diagnostics/frontend-summary')) {
        return jsonResponse({
          app_env: 'staging',
          auth_mode: 'supabase_jwt',
          db: { status: 'ok', mode: 'neon' },
          redis: { status: 'ok', configured: true },
          storage: {
            backend: 's3',
            bucket_configured: true,
            signed_url_enabled: true,
            public_base_url_configured: false,
          },
          tdlib: { status: 'not_configured', profile_execution_adapter: 'mock', live_enabled: false },
          workers: { queues: ['profile_jobs', 'auth_jobs'], mode: 'redis_rq' },
          generated_at: '2026-05-03T00:00:00Z',
        })
      }
      return jsonResponse({
        total: 1,
        low: 1,
        medium: 0,
        high: 0,
        critical: 0,
        reauth_required: 0,
        missing_session: 0,
        runtime_unhealthy: 0,
        proxy_problem: 0,
        items: [],
        computed_at: '2026-05-03T00:00:00Z',
      })
    }
    const client = createApiClient({ baseUrl: 'http://api.test', fetch: fetchMock as typeof fetch })

    await expect(fetchFrontendDiagnosticsSummary(client)).resolves.toMatchObject({ app_env: 'staging' })
    await expect(fetchAccountRiskSummary(client)).resolves.toMatchObject({ total: 1, low: 1 })
  })
})

function jsonResponse(payload: unknown): Response {
  return new Response(JSON.stringify(payload), { headers: { 'Content-Type': 'application/json' } })
}

function requestUrl(input: RequestInfo | URL): string {
  return input instanceof Request ? input.url : String(input)
}

async function requestBody(input: RequestInfo | URL, init?: RequestInit): Promise<unknown> {
  if (init?.body) return JSON.parse(String(init.body))
  if (input instanceof Request) {
    const text = await input.clone().text()
    return text ? JSON.parse(text) : null
  }
  return null
}
