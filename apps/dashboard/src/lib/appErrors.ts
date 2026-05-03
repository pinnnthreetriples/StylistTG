/**
 * Application-level error normalization utilities.
 *
 * These were previously inline in App.tsx.  Moving them here keeps the
 * component thin and makes the helpers testable in isolation.
 */

import type { ApiError } from '@/lib/http'

export function normalizeError(error: unknown): ApiError {
  if (isApiError(error)) {
    return error
  }
  if (isApiClientError(error)) {
    return {
      error_code: error.code ?? 'API_CLIENT_ERROR',
      error_class: 'api_client',
      message: error.message,
      details: isRecord(error.details) ? error.details : null,
      field_errors: [],
      request_id: 'frontend',
    }
  }

  return {
    error_code: 'NETWORK_ERROR',
    error_class: 'network',
    message: error instanceof Error ? error.message : 'unexpected frontend error',
    details: null,
    field_errors: [],
    request_id: 'frontend',
  }
}

export function isApiError(error: unknown): error is ApiError {
  return (
    typeof error === 'object' &&
    error !== null &&
    'error_code' in error &&
    'error_class' in error &&
    'message' in error
  )
}

function isApiClientError(error: unknown): error is { code?: string; message: string; details?: unknown } {
  return typeof error === 'object' && error !== null && 'message' in error && ('status' in error || 'code' in error)
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}
