import { accountHeader, headersToObject, newIdempotencyKey, unwrap } from './core'
import type {
  AccountRuntimeDiagnostics,
  AuthBatchCreate,
  AuthBatchEvent,
  AuthBatchItem,
  AuthBatchPhoneInput,
  AuthBatchPoll,
  AuthBatchRead,
  AuthBatchSnapshot,
  AuthBatchValidate,
  AuthRuntimeMode,
  AuthRuntimeModeUpdate,
  AuthState,
  RuntimeRefresh,
  StylistTgClient,
} from './types'
export async function refreshRuntime(client: StylistTgClient, accountId: string, init?: RequestInit): Promise<RuntimeRefresh> {
  return client.request<RuntimeRefresh>('/api/accounts/refresh-runtime', {
    ...init,
    method: 'POST',
    headers: { ...headersToObject(init?.headers), ...accountHeader(accountId) },
  })
}

export async function fetchAuthRuntimeMode(client: StylistTgClient): Promise<AuthRuntimeMode> {
  return unwrap(client.openapi.GET('/api/auth/runtime-mode'), 'auth runtime mode')
}

export async function updateAuthRuntimeMode(client: StylistTgClient, payload: AuthRuntimeModeUpdate): Promise<AuthRuntimeMode> {
  return unwrap(client.openapi.PATCH('/api/auth/runtime-mode', { body: payload }), 'update auth runtime mode')
}

export async function startOtp(client: StylistTgClient, phoneNumber: string): Promise<AuthState> {
  return unwrap(client.openapi.POST('/api/auth/otp/start', { body: { phone_number: phoneNumber } }), 'start otp')
}

export async function confirmOtp(client: StylistTgClient, accountId: string, code: string): Promise<AuthState> {
  return unwrap(client.openapi.POST('/api/auth/otp/confirm', { body: { account_id: accountId, code } }), 'confirm otp')
}

export async function submitPassword(client: StylistTgClient, accountId: string, password: string): Promise<AuthState> {
  return unwrap(client.openapi.POST('/api/auth/password', { body: { account_id: accountId, password } }), 'submit password')
}

export async function fetchAuthState(client: StylistTgClient, accountId: string): Promise<AuthState> {
  return unwrap(
    client.openapi.GET('/api/accounts/{account_id}/auth-state', {
      params: { path: { account_id: accountId } },
    }),
    'auth state',
  )
}

export async function validateAuthBatchPhones(
  client: StylistTgClient,
  items: AuthBatchPhoneInput[],
): Promise<AuthBatchValidate> {
  return unwrap(client.openapi.POST('/api/auth-batches/validate-phones', { body: { items } }), 'auth batch validation')
}

export async function createAuthBatch(client: StylistTgClient, payload: AuthBatchCreate): Promise<AuthBatchSnapshot> {
  return unwrap(client.openapi.POST('/api/auth-batches', { body: payload }), 'create auth batch')
}

export async function fetchAuthBatches(client: StylistTgClient): Promise<AuthBatchRead[]> {
  return unwrap(client.openapi.GET('/api/auth-batches'), 'auth batches')
}

export async function fetchAuthBatch(client: StylistTgClient, batchId: string): Promise<AuthBatchSnapshot> {
  return unwrap(
    client.openapi.GET('/api/auth-batches/{batch_id}', {
      params: { path: { batch_id: batchId } },
    }),
    'auth batch',
  )
}

export async function pollAuthBatch(client: StylistTgClient, batchId: string, sinceEventId?: string): Promise<AuthBatchPoll> {
  return unwrap(
    client.openapi.GET('/api/auth-batches/{batch_id}/poll', {
      params: { path: { batch_id: batchId }, query: sinceEventId ? { updated_since: sinceEventId } : undefined },
    }),
    'auth batch poll',
  )
}

export async function startAuthBatch(client: StylistTgClient, batchId: string): Promise<AuthBatchSnapshot> {
  return unwrap(
    client.openapi.POST('/api/auth-batches/{batch_id}/start', {
      params: { path: { batch_id: batchId } },
    }),
    'start auth batch',
  )
}

export async function pauseAuthBatch(client: StylistTgClient, batchId: string): Promise<AuthBatchSnapshot> {
  return unwrap(
    client.openapi.POST('/api/auth-batches/{batch_id}/pause', {
      params: { path: { batch_id: batchId } },
    }),
    'pause auth batch',
  )
}

export async function resumeAuthBatch(client: StylistTgClient, batchId: string): Promise<AuthBatchSnapshot> {
  return unwrap(
    client.openapi.POST('/api/auth-batches/{batch_id}/resume', {
      params: { path: { batch_id: batchId } },
    }),
    'resume auth batch',
  )
}

export async function cancelAuthBatch(client: StylistTgClient, batchId: string): Promise<AuthBatchSnapshot> {
  return unwrap(
    client.openapi.POST('/api/auth-batches/{batch_id}/cancel', {
      params: { path: { batch_id: batchId } },
    }),
    'cancel auth batch',
  )
}

export async function submitAuthBatchCode(
  client: StylistTgClient,
  batchId: string,
  itemId: string,
  code: string,
  idempotencyKey = newIdempotencyKey(),
): Promise<AuthBatchItem> {
  return unwrap(
    client.openapi.POST('/api/auth-batches/{batch_id}/items/{item_id}/submit-code', {
      params: { path: { batch_id: batchId, item_id: itemId } },
      body: { code, idempotency_key: idempotencyKey },
    }),
    'submit auth batch code',
  )
}

export async function submitAuthBatchPassword(
  client: StylistTgClient,
  batchId: string,
  itemId: string,
  password: string,
  idempotencyKey = newIdempotencyKey(),
): Promise<AuthBatchItem> {
  return unwrap(
    client.openapi.POST('/api/auth-batches/{batch_id}/items/{item_id}/submit-2fa', {
      params: { path: { batch_id: batchId, item_id: itemId } },
      body: { password, idempotency_key: idempotencyKey },
    }),
    'submit auth batch password',
  )
}

export async function retryAuthBatchItem(client: StylistTgClient, batchId: string, itemId: string): Promise<AuthBatchItem> {
  return unwrap(
    client.openapi.POST('/api/auth-batches/{batch_id}/items/{item_id}/retry', {
      params: { path: { batch_id: batchId, item_id: itemId } },
    }),
    'retry auth batch item',
  )
}

export async function requestNewAuthBatchCode(
  client: StylistTgClient,
  batchId: string,
  itemId: string,
): Promise<AuthBatchItem> {
  return unwrap(
    client.openapi.POST('/api/auth-batches/{batch_id}/items/{item_id}/request-new-code', {
      params: { path: { batch_id: batchId, item_id: itemId } },
    }),
    'request new auth batch code',
  )
}

export async function cancelAuthBatchItem(client: StylistTgClient, batchId: string, itemId: string): Promise<AuthBatchItem> {
  return unwrap(
    client.openapi.POST('/api/auth-batches/{batch_id}/items/{item_id}/cancel', {
      params: { path: { batch_id: batchId, item_id: itemId } },
    }),
    'cancel auth batch item',
  )
}

export async function fetchAuthBatchEvents(client: StylistTgClient, batchId: string, sinceEventId?: string): Promise<AuthBatchEvent[]> {
  void sinceEventId
  return unwrap(
    client.openapi.GET('/api/auth-batches/{batch_id}/events', {
      params: { path: { batch_id: batchId } },
    }),
    'auth batch events',
  )
}

export async function fetchAccountRuntimeDiagnostics(
  client: StylistTgClient,
  accountId: string,
): Promise<AccountRuntimeDiagnostics> {
  return unwrap(
    client.openapi.GET('/api/accounts/runtime-diagnostics', {
      params: { header: accountHeader(accountId) },
    }),
    'account runtime diagnostics',
  )
}
