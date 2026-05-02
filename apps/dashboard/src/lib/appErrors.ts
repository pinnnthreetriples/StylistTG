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
