import { getApiBaseUrl, getRequestTimeoutMs } from '@/lib/config'

export type ApiError = {
  error_code: string
  error_class: string
  message: string
  details: Record<string, unknown> | null
  field_errors: Array<{ field: string; message: string }>
  request_id: string
}

export type ApiRequestInit = RequestInit & {
  timeoutMs?: number
}

export async function apiRequest<T>(path: string, init?: ApiRequestInit): Promise<T> {
  const { timeoutMs, ...requestInit } = init ?? {}
  const controller = new AbortController()
  const timeoutId = globalThis.setTimeout(() => controller.abort(), timeoutMs ?? getRequestTimeoutMs())

  if (requestInit.signal) {
    requestInit.signal.addEventListener('abort', () => controller.abort(), { once: true })
  }

  try {
    const headers = buildRequestHeaders(requestInit)
    const response = await fetch(`${getApiBaseUrl()}${path}`, {
      ...requestInit,
      headers,
      signal: controller.signal,
    })
    const isJson = response.headers.get('content-type')?.includes('application/json')
    const payload: unknown = isJson && response.status !== 204 && response.status !== 205 ? await response.json() : null

    if (!response.ok) {
      throw isApiError(payload) ? payload : buildNetworkError(`request failed with status ${response.status}`)
    }

    return payload as T
  } catch (error) {
    if (isApiError(error)) {
      throw error
    }

    if (error instanceof DOMException && error.name === 'AbortError') {
      throw buildNetworkError('request timed out')
    }

    throw buildNetworkError(error instanceof Error ? error.message : 'network request failed')
  } finally {
    globalThis.clearTimeout(timeoutId)
  }
}

function buildRequestHeaders(requestInit: RequestInit): HeadersInit | undefined {
  if (typeof requestInit.body !== 'string') {
    return requestInit.headers
  }
  const headers = new Headers(requestInit.headers)
  if (headers.has('Content-Type')) {
    return requestInit.headers
  }
  return { ...headersInitToObject(requestInit.headers), 'Content-Type': 'application/json' }
}

function headersInitToObject(headers: HeadersInit | undefined): Record<string, string> {
  if (!headers) return {}
  if (headers instanceof Headers) {
    return Object.fromEntries(headers.entries())
  }
  if (Array.isArray(headers)) {
    return Object.fromEntries(headers)
  }
  return { ...headers }
}

export function isApiError(payload: unknown): payload is ApiError {
  return (
    typeof payload === 'object' &&
    payload !== null &&
    'error_code' in payload &&
    'error_class' in payload &&
    'message' in payload
  )
}

function buildNetworkError(message: string): ApiError {
  return {
    error_code: 'NETWORK_ERROR',
    error_class: 'network',
    message,
    details: null,
    field_errors: [],
    request_id: crypto.randomUUID?.() ?? 'frontend-network-error',
  }
}
