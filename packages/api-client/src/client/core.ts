import createClient from 'openapi-fetch'

import type { paths } from '../generated/schema'
import type { ApiClientError, ApiClientOptions, StylistTgClient } from './types'
export function resolveApiBaseUrl(value: string | undefined): string {
  if (!value) return ''
  return value.replace(/\/$/, '')
}

export function createApiClient(options: ApiClientOptions = {}): StylistTgClient {
  const baseUrl = resolveApiBaseUrl(options.baseUrl)
  const fetchWithAuth = createFetchWithAuth(options.fetch ?? globalThis.fetch.bind(globalThis), options.getAccessToken)
  return {
    baseUrl,
    openapi: createClient<paths>({
      baseUrl,
      fetch: fetchWithAuth,
    }),
    request: async <T>(path: string, init?: RequestInit) => {
      const response = await fetchWithAuth(buildUrl(baseUrl, path), init)
      return readResponse<T>(response)
    },
    buildUrl: (path: string) => buildUrl(baseUrl, path),
  }
}

export const createStylistTgClient = createApiClient

function createFetchWithAuth(baseFetch: typeof fetch, getAccessToken: ApiClientOptions['getAccessToken']): typeof fetch {
  return async (input, init) => {
    const headers = new Headers(init?.headers ?? (input instanceof Request ? input.headers : undefined))
    const token = await getAccessToken?.()
    if (token && !headers.has('Authorization')) {
      headers.set('Authorization', `Bearer ${token}`)
    }
    const body = init?.body ?? (input instanceof Request ? input.body : undefined)
    if (shouldDefaultJsonContentType(body) && !headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json')
    }
    return baseFetch(input, { ...init, headers })
  }
}

function shouldDefaultJsonContentType(body: unknown): boolean {
  if (body === undefined || body === null) return false
  if (typeof FormData !== 'undefined' && body instanceof FormData) return false
  if (typeof URLSearchParams !== 'undefined' && body instanceof URLSearchParams) return false
  if (typeof Blob !== 'undefined' && body instanceof Blob) return false
  if (body instanceof ArrayBuffer) return false
  if (ArrayBuffer.isView(body)) return false
  return true
}

export function buildUrl(baseUrl: string, path: string): string {
  if (/^https?:\/\//i.test(path)) return path
  return `${baseUrl}${path.startsWith('/') ? path : `/${path}`}`
}

async function readResponse<T>(response: Response): Promise<T> {
  const isJson = response.headers.get('content-type')?.includes('application/json')
  const payload = isJson && response.status !== 204 && response.status !== 205 ? await response.json() : null
  if (!response.ok) {
    throw normalizeClientError(payload, response.status)
  }
  return payload as T
}

export function normalizeClientError(error: unknown, status?: number): ApiClientError {
  if (typeof error === 'object' && error !== null) {
    const record = error as Record<string, unknown>
    return {
      status,
      code: typeof record.error_code === 'string' ? record.error_code : undefined,
      message: typeof record.message === 'string' ? record.message : `request failed${status ? ` with status ${status}` : ''}`,
      details: record.details ?? error,
    }
  }
  return {
    status,
    message: error instanceof Error ? error.message : `request failed${status ? ` with status ${status}` : ''}`,
  }
}

export async function unwrap<T>(promise: Promise<{ data?: T; error?: unknown; response: Response }>, label: string): Promise<T> {
  const { data, error, response } = await promise
  if (error) {
    const normalized = normalizeClientError(error, response.status)
    throw { ...normalized, message: normalized.message || `${label} request failed` }
  }
  if (!response.ok || data === undefined) {
    const normalized = normalizeClientError(null, response.status)
    throw { ...normalized, message: `${label} request failed with status ${response.status}` }
  }
  return data
}

export function accountHeader(accountId: string): { 'X-Account-Id': string } {
  return { 'X-Account-Id': accountId }
}

export function headersToObject(headers: RequestInit['headers']): Record<string, string> {
  if (!headers) return {}
  if (headers instanceof Headers) return Object.fromEntries(headers.entries())
  if (Array.isArray(headers)) return Object.fromEntries(headers)
  return Object.fromEntries(Object.entries(headers).filter((entry): entry is [string, string] => typeof entry[1] === 'string'))
}

export function newIdempotencyKey(): string {
  return globalThis.crypto?.randomUUID?.() ?? `request-${Date.now()}-${Math.random().toString(16).slice(2)}`
}
