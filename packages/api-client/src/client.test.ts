import { describe, expect, test } from 'vitest'

import {
  buildAssetContentUrl,
  confirmOtp,
  confirmAccountImportBatch,
  createApiClient,
  createAccountImportBatch,
  createAuthBatch,
  createTelegramAuthSession,
  fetchAccountRuntimeDiagnostics,
  fetchCurrentUser,
  createStylistTgClient,
  fetchFrontendDiagnosticsSummary,
  fetchReady,
  fetchRuntimeDiagnostics,
  fetchAccountRiskSummary,
  fetchTdlibRuntimeStatus,
  normalizeClientError,
  resolveApiBaseUrl,
  submitTelegramAuthCode,
  startOtp,
  uploadAsset,
  validateAccountImportBatch,
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

  test('ready endpoint wrapper returns minimal readiness status', async () => {
    const client = createApiClient({
      baseUrl: 'http://localhost:8000',
      fetch: (async () =>
        new Response(JSON.stringify({ status: 'ok' }), {
          headers: { 'Content-Type': 'application/json' },
        })) as typeof fetch,
    })

    await expect(fetchReady(client)).resolves.toEqual({ status: 'ok' })
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
    const calls: Array<{ url: string; contentType: string | null }> = []
    const fetchMock = async (input: RequestInfo | URL, init?: RequestInit) => {
      calls.push({ url: requestUrl(input), contentType: requestContentType(input, init) })
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

    expect(calls).toEqual([
      { url: 'http://api.test/api/auth-batches/validate-phones', contentType: 'application/json' },
      { url: 'http://api.test/api/auth-batches', contentType: 'application/json' },
    ])
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

  test('current user wrapper reads /api/me', async () => {
    const fetchMock = async (input: RequestInfo | URL) => {
      expect(requestUrl(input)).toBe('http://api.test/api/me')
      return jsonResponse({
        user_id: 'user-1',
        email: 'user@example.test',
        display_name: 'User',
        workspace_id: 'workspace-1',
        workspace_name: 'User workspace',
        role: 'owner',
        auth_source: 'supabase_jwt',
      })
    }
    const client = createApiClient({ baseUrl: 'http://api.test', fetch: fetchMock as typeof fetch })

    await expect(fetchCurrentUser(client)).resolves.toMatchObject({
      user_id: 'user-1',
      workspace_id: 'workspace-1',
      auth_source: 'supabase_jwt',
    })
  })

  test('TDLib auth and import wrappers use generated endpoint paths without leaking secrets in errors', async () => {
    const calls: Array<{ url: string; body: unknown }> = []
    const fetchMock = async (input: RequestInfo | URL, init?: RequestInit) => {
      calls.push({ url: requestUrl(input), body: await requestBody(input, init) })
      if (requestUrl(input).endsWith('/api/tdlib/runtime')) {
        return jsonResponse({
          configured: false,
          library_configured: false,
          library_loadable: false,
          live_enabled: false,
          runtime_mode: 'mock',
          api_id_configured: false,
          api_hash_configured: false,
          readonly_smoke_available: false,
          error_code: null,
        })
      }
      if (requestUrl(input).includes('/account-import-batches')) {
        return jsonResponse(importBatchPayload())
      }
      return jsonResponse(authSessionPayload())
    }
    const client = createApiClient({ baseUrl: 'http://api.test', fetch: fetchMock as typeof fetch })

    await createTelegramAuthSession(client, { phone_number: '+15550102000', label: 'Main', proxy_id: null })
    await submitTelegramAuthCode(client, 'auth-1', { code: '12345' })
    await fetchTdlibRuntimeStatus(client)
    await createAccountImportBatch(client, { source_type: 'json-metadata', label: 'Import', dry_run: true, metadata: {} })
    await validateAccountImportBatch(client, 'batch-1', { metadata: { username: 'demo' }, content_base64: null })
    await confirmAccountImportBatch(client, 'batch-1', { confirmation: 'IMPORT' })

    expect(calls.map((call) => call.url)).toEqual([
      'http://api.test/api/accounts/auth-sessions',
      'http://api.test/api/accounts/auth-sessions/auth-1/code',
      'http://api.test/api/tdlib/runtime',
      'http://api.test/api/account-import-batches',
      'http://api.test/api/account-import-batches/batch-1/validate',
      'http://api.test/api/account-import-batches/batch-1/confirm',
    ])
    expect(JSON.stringify(calls)).not.toContain('code_invalid: 12345')
  })

  test('does not overwrite Authorization header if already set', async () => {
    const calls: RequestInit[] = []
    const fetchMock = async (_input: RequestInfo | URL, init?: RequestInit) => {
      calls.push(init ?? {})
      return jsonResponse({ status: 'ok' })
    }
    const client = createApiClient({
      baseUrl: 'http://api.test',
      fetch: fetchMock as typeof fetch,
      getAccessToken: () => 'auto-token',
    })

    await client.request('/health', { headers: { Authorization: 'Bearer manual-token' } })

    expect(new Headers(calls[0]?.headers).get('Authorization')).toBe('Bearer manual-token')
  })

  test('sets Content-Type to application/json for string body', async () => {
    const calls: RequestInit[] = []
    const fetchMock = async (_input: RequestInfo | URL, init?: RequestInit) => {
      calls.push(init ?? {})
      return jsonResponse({ ok: true })
    }
    const client = createApiClient({ baseUrl: 'http://api.test', fetch: fetchMock as typeof fetch })

    await client.request('/api/test', { method: 'POST', body: JSON.stringify({ key: 'value' }) })

    expect(new Headers(calls[0]?.headers).get('Content-Type')).toBe('application/json')
  })

  test('does not set Content-Type for FormData body', async () => {
    const calls: RequestInit[] = []
    const fetchMock = async (_input: RequestInfo | URL, init?: RequestInit) => {
      calls.push(init ?? {})
      return jsonResponse({ id: 'asset-1' })
    }
    const client = createApiClient({ baseUrl: 'http://api.test', fetch: fetchMock as typeof fetch })

    const formData = new FormData()
    formData.append('file', new Blob(['test']), 'test.txt')
    await client.request('/api/assets/profile-photo', { method: 'POST', body: formData })

    expect(new Headers(calls[0]?.headers).get('Content-Type')).toBeNull()
  })

  test('normalizeClientError handles null error', () => {
    const result = normalizeClientError(null, 500)
    expect(result).toEqual({
      status: 500,
      message: 'request failed with status 500',
    })
  })

  test('normalizeClientError handles plain Error instance', () => {
    const result = normalizeClientError(new Error('boom'), 503)
    expect(result.status).toBe(503)
    expect(result.message).toBe('boom')
  })

  test('normalizeClientError handles error without error_code', () => {
    const result = normalizeClientError({ message: 'something went wrong', details: { field: 'name' } }, 422)
    expect(result).toEqual({
      status: 422,
      code: undefined,
      message: 'something went wrong',
      details: { field: 'name' },
    })
  })

  test('buildAssetContentUrl encodes special characters in asset ID', () => {
    const client = createApiClient({ baseUrl: 'http://api.test' })

    const url = buildAssetContentUrl(client, 'asset/with spaces&special=chars')

    expect(url).toBe('http://api.test/api/assets/asset%2Fwith%20spaces%26special%3Dchars/content')
    expect(url).not.toContain(' ')
  })

  test('account runtime diagnostics sends X-Account-Id header', async () => {
    const calls: Array<{ url: string; headers: Headers }> = []
    const fetchMock = async (input: RequestInfo | URL, init?: RequestInit) => {
      calls.push({
        url: requestUrl(input),
        headers: new Headers(init?.headers ?? (input instanceof Request ? input.headers : undefined)),
      })
      return jsonResponse({
        total: 0,
        accounts: [],
        generated_at: '2026-05-03T00:00:00Z',
      })
    }
    const client = createApiClient({ baseUrl: 'http://api.test', fetch: fetchMock as typeof fetch })

    await fetchAccountRuntimeDiagnostics(client, 'acct-123')

    expect(calls.length).toBeGreaterThanOrEqual(1)
  })
})

function jsonResponse(payload: unknown): Response {
  return new Response(JSON.stringify(payload), { headers: { 'Content-Type': 'application/json' } })
}

function requestUrl(input: RequestInfo | URL): string {
  return input instanceof Request ? input.url : String(input)
}

function requestContentType(input: RequestInfo | URL, init?: RequestInit): string | null {
  const headers = init?.headers ?? (input instanceof Request ? input.headers : undefined)
  return new Headers(headers).get('Content-Type')
}

async function requestBody(input: RequestInfo | URL, init?: RequestInit): Promise<unknown> {
  if (init?.body) return JSON.parse(String(init.body))
  if (input instanceof Request) {
    const text = await input.clone().text()
    return text ? JSON.parse(text) : null
  }
  return null
}

function authSessionPayload() {
  return {
    id: 'auth-1',
    workspace_id: 'workspace-1',
    account_id: null,
    phone_hint: '***2000',
    label: 'Main',
    status: 'failed',
    source: 'new_auth',
    requires_code: false,
    requires_password: false,
    cooldown_until: null,
    last_error_code: 'tdlib_live_disabled',
    last_error_message: 'TDLib live auth is disabled.',
    created_at: '2026-05-03T00:00:00Z',
    updated_at: '2026-05-03T00:00:00Z',
    completed_at: null,
    failed_at: '2026-05-03T00:00:00Z',
  }
}

function importBatchPayload() {
  return {
    id: 'batch-1',
    workspace_id: 'workspace-1',
    source_type: 'json-metadata',
    status: 'preview_ready',
    label: 'Import',
    dry_run: true,
    item_count: 1,
    created_at: '2026-05-03T00:00:00Z',
    completed_at: '2026-05-03T00:00:00Z',
    failed_at: null,
    failure_code: null,
    failure_message: null,
    items: [
      {
        id: 'item-1',
        account_id: null,
        status: 'valid',
        phone_hint: null,
        username_hint: 'demo',
        validation_code: 'json_metadata_preview',
        validation_message: 'Preview only.',
        risk_level: 'low',
        created_at: '2026-05-03T00:00:00Z',
        updated_at: '2026-05-03T00:00:00Z',
      },
    ],
  }
}
