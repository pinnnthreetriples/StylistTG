import { unwrap } from './core'
import type {
  AccountImportBatch,
  AccountImportBatchConfirm,
  AccountImportBatchCreate,
  AccountImportBatchValidate,
  StylistTgClient,
  TdlibRuntimeStatus,
  TelegramAuthCodeSubmit,
  TelegramAuthPasswordSubmit,
  TelegramAuthSession,
  TelegramAuthSessionCreate,
} from './types'
export async function fetchTdlibRuntimeStatus(client: StylistTgClient): Promise<TdlibRuntimeStatus> {
  return unwrap(client.openapi.GET('/api/tdlib/runtime'), 'TDLib runtime')
}

export async function createTelegramAuthSession(
  client: StylistTgClient,
  payload: TelegramAuthSessionCreate,
): Promise<TelegramAuthSession> {
  return unwrap(client.openapi.POST('/api/accounts/auth-sessions', { body: payload }), 'create Telegram auth session')
}

export async function fetchTelegramAuthSessions(client: StylistTgClient): Promise<TelegramAuthSession[]> {
  return unwrap(client.openapi.GET('/api/accounts/auth-sessions'), 'Telegram auth sessions')
}

export async function fetchTelegramAuthSession(client: StylistTgClient, authSessionId: string): Promise<TelegramAuthSession> {
  return unwrap(
    client.openapi.GET('/api/accounts/auth-sessions/{auth_session_id}', {
      params: { path: { auth_session_id: authSessionId } },
    }),
    'Telegram auth session',
  )
}

export async function submitTelegramAuthCode(
  client: StylistTgClient,
  authSessionId: string,
  payload: TelegramAuthCodeSubmit,
): Promise<TelegramAuthSession> {
  return unwrap(
    client.openapi.POST('/api/accounts/auth-sessions/{auth_session_id}/code', {
      params: { path: { auth_session_id: authSessionId } },
      body: payload,
    }),
    'submit Telegram auth code',
  )
}

export async function submitTelegramAuthPassword(
  client: StylistTgClient,
  authSessionId: string,
  payload: TelegramAuthPasswordSubmit,
): Promise<TelegramAuthSession> {
  return unwrap(
    client.openapi.POST('/api/accounts/auth-sessions/{auth_session_id}/password', {
      params: { path: { auth_session_id: authSessionId } },
      body: payload,
    }),
    'submit Telegram auth password',
  )
}

export async function cancelTelegramAuthSession(client: StylistTgClient, authSessionId: string): Promise<TelegramAuthSession> {
  return unwrap(
    client.openapi.POST('/api/accounts/auth-sessions/{auth_session_id}/cancel', {
      params: { path: { auth_session_id: authSessionId } },
    }),
    'cancel Telegram auth session',
  )
}

export async function createReauthSession(
  client: StylistTgClient,
  accountId: string,
  payload: TelegramAuthSessionCreate,
): Promise<TelegramAuthSession> {
  return unwrap(
    client.openapi.POST('/api/accounts/{account_id}/reauth-sessions', {
      params: { path: { account_id: accountId } },
      body: payload,
    }),
    'create Telegram reauth session',
  )
}

export async function createAccountImportBatch(
  client: StylistTgClient,
  payload: AccountImportBatchCreate,
): Promise<AccountImportBatch> {
  return unwrap(client.openapi.POST('/api/account-import-batches', { body: payload }), 'create account import batch')
}

export async function fetchAccountImportBatches(client: StylistTgClient): Promise<AccountImportBatch[]> {
  return unwrap(client.openapi.GET('/api/account-import-batches'), 'account import batches')
}

export async function fetchAccountImportBatch(client: StylistTgClient, batchId: string): Promise<AccountImportBatch> {
  return unwrap(
    client.openapi.GET('/api/account-import-batches/{batch_id}', {
      params: { path: { batch_id: batchId } },
    }),
    'account import batch',
  )
}

export async function validateAccountImportBatch(
  client: StylistTgClient,
  batchId: string,
  payload: AccountImportBatchValidate,
): Promise<AccountImportBatch> {
  return unwrap(
    client.openapi.POST('/api/account-import-batches/{batch_id}/validate', {
      params: { path: { batch_id: batchId } },
      body: payload,
    }),
    'validate account import batch',
  )
}

export async function confirmAccountImportBatch(
  client: StylistTgClient,
  batchId: string,
  payload: AccountImportBatchConfirm,
): Promise<AccountImportBatch> {
  return unwrap(
    client.openapi.POST('/api/account-import-batches/{batch_id}/confirm', {
      params: { path: { batch_id: batchId } },
      body: payload,
    }),
    'confirm account import batch',
  )
}
