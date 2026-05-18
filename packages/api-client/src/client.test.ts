import { describe, expect, test } from 'vitest'

import {
  addNeuroCampaignAccount,
  addNeuroCampaignTarget,
  approveNeuroGeneratedComment,
  buildAssetContentUrl,
  confirmOtp,
  confirmAccountImportBatch,
  createApiClient,
  createAccountImportBatch,
  createAuthBatch,
  createNeuroCampaign,
  createTelegramAuthSession,
  deleteNeuroCampaignAccount,
  deleteNeuroCampaignTarget,
  editNeuroGeneratedComment,
  fetchAccountRuntimeDiagnostics,
  fetchCurrentUser,
  createStylistTgClient,
  fetchFrontendDiagnosticsSummary,
  fetchNeuroCampaign,
  fetchNeuroCampaignAccounts,
  fetchNeuroCampaigns,
  fetchNeuroCampaignTargets,
  fetchNeuroAttempt,
  fetchNeuroAttempts,
  fetchNeuroEvents,
  fetchNeuroGeneratedComment,
  fetchNeuroGeneratedComments,
  fetchNeuroObservedPost,
  fetchNeuroObservedPosts,
  fetchReady,
  fetchRuntimeDiagnostics,
  fetchAccountRiskSummary,
  fetchTdlibRuntimeStatus,
  generateNeuroObservedPost,
  normalizeClientError,
  observeNeuroCampaign,
  observeNeuroTarget,
  pauseNeuroCampaign,
  rejectNeuroGeneratedComment,
  refreshNeuroTargetMetadata,
  resolveApiBaseUrl,
  sendNeuroGeneratedComment,
  startNeuroCampaign,
  stopNeuroCampaign,
  submitTelegramAuthCode,
  startOtp,
  updateNeuroCampaign,
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

  test('neuro-commenting campaign CRUD wrappers hit correct endpoints', async () => {
    const calls: Array<{ method: string; url: string }> = []
    const fetchMock = async (input: RequestInfo | URL, init?: RequestInit) => {
      calls.push({ method: requestMethod(input, init), url: requestUrl(input) })
      return jsonResponse(neuroCampaignPayload())
    }
    const client = createApiClient({ baseUrl: 'http://api.test', fetch: fetchMock as typeof fetch })

    await fetchNeuroCampaigns(client)
    await createNeuroCampaign(client, neuroCampaignCreatePayload())
    await fetchNeuroCampaign(client, 'camp-1')
    await updateNeuroCampaign(client, 'camp-1', { name: 'Updated' })

    expect(calls.map((c) => `${c.method} ${c.url}`)).toEqual([
      'GET http://api.test/api/neuro-commenting/campaigns',
      'POST http://api.test/api/neuro-commenting/campaigns',
      'GET http://api.test/api/neuro-commenting/campaigns/camp-1',
      'PATCH http://api.test/api/neuro-commenting/campaigns/camp-1',
    ])
  })

  test('neuro-commenting campaign lifecycle wrappers', async () => {
    const calls: Array<{ url: string }> = []
    const fetchMock = async (input: RequestInfo | URL) => {
      calls.push({ url: requestUrl(input) })
      return jsonResponse(neuroCampaignPayload())
    }
    const client = createApiClient({ baseUrl: 'http://api.test', fetch: fetchMock as typeof fetch })

    await startNeuroCampaign(client, 'camp-1')
    await pauseNeuroCampaign(client, 'camp-1')
    await stopNeuroCampaign(client, 'camp-1')

    expect(calls.map((c) => c.url)).toEqual([
      'http://api.test/api/neuro-commenting/campaigns/camp-1/start',
      'http://api.test/api/neuro-commenting/campaigns/camp-1/pause',
      'http://api.test/api/neuro-commenting/campaigns/camp-1/stop',
    ])
  })

  test('neuro-commenting accounts and targets wrappers', async () => {
    const calls: Array<{ method: string; url: string }> = []
    const fetchMock = async (input: RequestInfo | URL, init?: RequestInit) => {
      const method = requestMethod(input, init)
      calls.push({ method, url: requestUrl(input) })
      if (method === 'DELETE') return new Response(null, { status: 204 })
      if (requestUrl(input).includes('/accounts')) {
        return jsonResponse({ items: [], total: 0, page: 1, limit: 50 })
      }
      return jsonResponse({ items: [], total: 0, page: 1, limit: 50 })
    }
    const client = createApiClient({ baseUrl: 'http://api.test', fetch: fetchMock as typeof fetch })

    await fetchNeuroCampaignAccounts(client, 'camp-1')
    await addNeuroCampaignAccount(client, 'camp-1', { account_id: 'acct-1', rotation_weight: 1, rotation_order: 0 })
    await deleteNeuroCampaignAccount(client, 'camp-1', 'acct-1')
    await fetchNeuroCampaignTargets(client, 'camp-1')
    await addNeuroCampaignTarget(client, 'camp-1', { channel_ref: '@test', source_type: 'channel' })
    await deleteNeuroCampaignTarget(client, 'camp-1', 'target-1')

    expect(calls.map((c) => `${c.method} ${c.url}`)).toEqual([
      'GET http://api.test/api/neuro-commenting/campaigns/camp-1/accounts',
      'POST http://api.test/api/neuro-commenting/campaigns/camp-1/accounts',
      'DELETE http://api.test/api/neuro-commenting/campaigns/camp-1/accounts/acct-1',
      'GET http://api.test/api/neuro-commenting/campaigns/camp-1/targets',
      'POST http://api.test/api/neuro-commenting/campaigns/camp-1/targets',
      'DELETE http://api.test/api/neuro-commenting/campaigns/camp-1/targets/target-1',
    ])
  })

  test('neuro-commenting generated comments wrappers', async () => {
    const calls: Array<{ method: string; url: string }> = []
    const commentPayload = neuroGeneratedCommentPayload()
    const fetchMock = async (input: RequestInfo | URL, init?: RequestInit) => {
      calls.push({ method: requestMethod(input, init), url: requestUrl(input) })
      if (requestUrl(input).endsWith('/generated-comments') || requestUrl(input).includes('campaign_id')) {
        return jsonResponse({ items: [commentPayload], total: 1, page: 1, limit: 50 })
      }
      return jsonResponse(commentPayload)
    }
    const client = createApiClient({ baseUrl: 'http://api.test', fetch: fetchMock as typeof fetch })

    await fetchNeuroGeneratedComments(client)
    await fetchNeuroGeneratedComments(client, { campaign_id: 'camp-1' })
    await fetchNeuroGeneratedComment(client, 'comment-1')
    await editNeuroGeneratedComment(client, 'comment-1', { edited_text: 'edited' })
    await approveNeuroGeneratedComment(client, 'comment-1')
    await rejectNeuroGeneratedComment(client, 'comment-1', { reason: 'off-topic' })
    await sendNeuroGeneratedComment(client, 'comment-1')

    expect(calls.length).toBe(7)
    expect(calls[0].url).toContain('/generated-comments')
    expect(calls[3].method).toBe('PATCH')
    expect(calls[4].url).toContain('/approve')
    expect(calls[5].url).toContain('/reject')
    expect(calls[6].url).toContain('/send')
  })

  test('neuro-commenting observed posts wrappers hit correct endpoints', async () => {
    const calls: Array<{ method: string; url: string }> = []
    const fetchMock = async (input: RequestInfo | URL, init?: RequestInit) => {
      calls.push({ method: requestMethod(input, init), url: requestUrl(input) })
      if (requestUrl(input).endsWith('/observed-posts') || requestUrl(input).includes('campaign_id')) {
        return jsonResponse({ items: [], total: 0, page: 1, limit: 50 })
      }
      return jsonResponse(neuroObservedPostPayload())
    }
    const client = createApiClient({ baseUrl: 'http://api.test', fetch: fetchMock as typeof fetch })

    await fetchNeuroObservedPosts(client, { campaign_id: 'camp-1', target_id: 'target-1' })
    await fetchNeuroObservedPost(client, 'post-1')
    await generateNeuroObservedPost(client, 'post-1')

    expect(calls.map((c) => `${c.method} ${c.url}`)).toEqual([
      'GET http://api.test/api/neuro-commenting/observed-posts?campaign_id=camp-1&target_id=target-1',
      'GET http://api.test/api/neuro-commenting/observed-posts/post-1',
      'POST http://api.test/api/neuro-commenting/observed-posts/post-1/generate',
    ])
  })

  test('neuro-commenting observe target and refresh wrappers hit correct endpoints', async () => {
    const calls: Array<{ method: string; url: string }> = []
    const fetchMock = async (input: RequestInfo | URL, init?: RequestInit) => {
      calls.push({ method: requestMethod(input, init), url: requestUrl(input) })
      return jsonResponse({ accepted: true, job_id: 'job-1', queue_name: 'neuro_comment_jobs' })
    }
    const client = createApiClient({ baseUrl: 'http://api.test', fetch: fetchMock as typeof fetch })

    await observeNeuroCampaign(client, 'camp-1')
    await observeNeuroTarget(client, 'camp-1', 'target-1', { generate: false })
    await refreshNeuroTargetMetadata(client, 'camp-1', 'target-1')

    expect(calls.map((c) => `${c.method} ${c.url}`)).toEqual([
      'POST http://api.test/api/neuro-commenting/campaigns/camp-1/observe',
      'POST http://api.test/api/neuro-commenting/campaigns/camp-1/targets/target-1/observe',
      'POST http://api.test/api/neuro-commenting/campaigns/camp-1/targets/target-1/refresh-metadata',
    ])
  })

  test('neuro-commenting attempts wrappers hit correct endpoints', async () => {
    const calls: Array<{ method: string; url: string }> = []
    const fetchMock = async (input: RequestInfo | URL, init?: RequestInit) => {
      calls.push({ method: requestMethod(input, init), url: requestUrl(input) })
      if (requestUrl(input).endsWith('/attempts') || requestUrl(input).includes('campaign_id')) {
        return jsonResponse({ items: [], total: 0, page: 1, limit: 50 })
      }
      return jsonResponse(neuroAttemptPayload())
    }
    const client = createApiClient({ baseUrl: 'http://api.test', fetch: fetchMock as typeof fetch })

    await fetchNeuroAttempts(client, { campaign_id: 'camp-1', generated_comment_id: 'comment-1' })
    await fetchNeuroAttempt(client, 'attempt-1')

    expect(calls.map((c) => `${c.method} ${c.url}`)).toEqual([
      'GET http://api.test/api/neuro-commenting/attempts?campaign_id=camp-1&generated_comment_id=comment-1',
      'GET http://api.test/api/neuro-commenting/attempts/attempt-1',
    ])
  })

  test('neuro-commenting events wrapper', async () => {
    const fetchMock = async () => jsonResponse({ items: [], total: 0, page: 1, limit: 50 })
    const client = createApiClient({ baseUrl: 'http://api.test', fetch: fetchMock as typeof fetch })

    const result = await fetchNeuroEvents(client)
    expect(result).toEqual({ items: [], total: 0, page: 1, limit: 50 })
  })

  test('account runtime diagnostics sends X-Account-Id header', async () => {
    const calls: Array<{ url: string; accountId: string | null }> = []
    const fetchMock = async (input: RequestInfo | URL, init?: RequestInit) => {
      const headers = input instanceof Request
        ? input.headers
        : new Headers(init?.headers)
      calls.push({
        url: requestUrl(input),
        accountId: headers.get('X-Account-Id'),
      })
      return jsonResponse({
        total: 0,
        accounts: [],
        generated_at: '2026-05-03T00:00:00Z',
      })
    }
    const client = createApiClient({ baseUrl: 'http://api.test', fetch: fetchMock as typeof fetch })

    await fetchAccountRuntimeDiagnostics(client, 'acct-123')

    expect(calls.length).toBe(1)
    expect(calls[0].accountId).toBe('acct-123')
  })
})

function jsonResponse(payload: unknown): Response {
  return new Response(JSON.stringify(payload), { headers: { 'Content-Type': 'application/json' } })
}

function requestUrl(input: RequestInfo | URL): string {
  return input instanceof Request ? input.url : String(input)
}

function requestMethod(input: RequestInfo | URL, init?: RequestInit): string {
  if (init?.method) return init.method
  if (input instanceof Request) return input.method
  return 'GET'
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

function neuroCampaignPayload() {
  return {
    items: [{ id: 'camp-1', workspace_id: 'ws-1', name: 'Test', status: 'draft' }],
    total: 1,
    page: 1,
    limit: 50,
  }
}

function neuroCampaignCreatePayload() {
  return {
    name: 'Test Campaign',
    mode: 'all_posts' as const,
    work_mode: 'manual' as const,
    approval_mode: 'manual_required' as const,
    send_mode: 'dry_run' as const,
    send_strategy: 'comment' as const,
    rotation_strategy: 'round_robin' as const,
    language_mode: 'auto',
    delay_min_seconds: 60,
    delay_max_seconds: 300,
    dry_run: true,
    auto_send_enabled: false as const,
    safety_enabled: true,
  }
}

function neuroGeneratedCommentPayload() {
  return {
    id: 'comment-1',
    campaign_id: 'camp-1',
    workspace_id: 'ws-1',
    final_text: 'Test comment',
    approval_status: 'pending',
    created_at: '2026-05-18T00:00:00Z',
    updated_at: null,
  }
}

function neuroObservedPostPayload() {
  return {
    id: 'post-1',
    campaign_id: 'camp-1',
    target_id: 'target-1',
    source_chat_id: 'chat-1',
    source_message_id: 'msg-1',
    post_text: 'Observed post',
    media_summary: null,
    language: 'en',
    matched_mode: 'all_posts',
    matched_keywords: [],
    status: 'seen',
    seen_at: '2026-05-18T00:00:00Z',
    processed_at: null,
    created_at: '2026-05-18T00:00:00Z',
    updated_at: '2026-05-18T00:00:00Z',
  }
}

function neuroAttemptPayload() {
  return {
    id: 'attempt-1',
    campaign_id: 'camp-1',
    generated_comment_id: 'comment-1',
    account_id: 'account-1',
    target_id: 'target-1',
    observed_post_id: 'post-1',
    status: 'created',
    send_strategy: 'comment',
    telegram_message_id: null,
    error_code: null,
    error_message: null,
    flood_wait_seconds: null,
    reserved_limit_at: null,
    sent_at: null,
    failed_at: null,
    created_at: '2026-05-18T00:00:00Z',
    updated_at: '2026-05-18T00:00:00Z',
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
