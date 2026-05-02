import createClient, { type Client } from 'openapi-fetch'

import type { paths } from './generated/schema'

export type StylistTgClient = Client<paths>

export type ApiClientOptions = {
  baseUrl?: string
  fetch?: typeof fetch
}

export function resolveApiBaseUrl(value: string | undefined): string {
  if (!value) return ''
  return value.replace(/\/$/, '')
}

export function createStylistTgClient(options: ApiClientOptions = {}): StylistTgClient {
  return createClient<paths>({
    baseUrl: resolveApiBaseUrl(options.baseUrl),
    fetch: options.fetch,
  })
}

export type AccountListItem = {
  account_id: string
  display_name: string | null
  username: string | null
  phone_number: string
  telegram_user_id: string | null
  account_state: string
  runtime_health: string
  is_execution_usable: boolean
  is_test_dc: boolean
  profile_photo_asset_id: string | null
  updated_at: string
}

export type JobSummary = {
  job_id: string
  job_state: string
  execution_intent_hash: string
  plan_summary: string[]
  created_at: string | null
  dedup_blocked_by_job_id: string | null
  message: string | null
}

export type RuntimeDiagnostics = {
  database: string
  redis: string
  tdlib: string
}

export async function fetchAccounts(client: StylistTgClient): Promise<AccountListItem[]> {
  const { data, error, response } = await client.GET('/api/accounts')
  if (error) {
    throw error
  }
  if (!response.ok || !data) {
    throw new Error(`accounts request failed with status ${response.status}`)
  }
  return data as AccountListItem[]
}

export async function fetchLatestJobs(
  client: StylistTgClient,
  accountId: string,
  limit = 10,
): Promise<JobSummary[]> {
  const { data, error, response } = await client.GET('/api/accounts/jobs', {
    params: {
      header: { 'X-Account-Id': accountId },
      query: { limit },
    },
  })
  if (error) {
    throw error
  }
  if (!response.ok || !data) {
    throw new Error(`jobs request failed with status ${response.status}`)
  }
  return data as JobSummary[]
}

export async function fetchRuntimeDiagnostics(client: StylistTgClient): Promise<RuntimeDiagnostics> {
  const { data, error, response } = await client.GET('/diagnostics/runtime')
  if (error) {
    throw error
  }
  if (!response.ok || !data) {
    throw new Error(`diagnostics request failed with status ${response.status}`)
  }
  return data as RuntimeDiagnostics
}
