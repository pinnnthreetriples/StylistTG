import { apiRequest } from '@/lib/http'

import type {
  WarmupEventPage,
  WarmupIsolationStatus,
  WarmupReadiness,
  WarmupSessionDetail,
  WarmupSessionPage,
  WarmupStrategy,
  WarmupValidateResponse,
} from './types'

export function fetchWarmupReadiness(): Promise<WarmupReadiness> {
  return apiRequest('/api/warmup/readiness')
}

export function fetchWarmupStrategies(): Promise<WarmupStrategy[]> {
  return apiRequest('/api/warmup/strategies')
}

export function fetchWarmupSessions(params?: { page?: number; limit?: number }): Promise<WarmupSessionPage> {
  const query = new URLSearchParams()
  if (params?.page != null) query.set('page', String(params.page))
  if (params?.limit != null) query.set('limit', String(params.limit))
  const qs = query.toString()
  return apiRequest(`/api/warmup/sessions${qs ? `?${qs}` : ''}`)
}

export function validateWarmup(accountId: string, strategyId: string): Promise<WarmupValidateResponse> {
  return apiRequest('/api/warmup/validate', {
    method: 'POST',
    body: JSON.stringify({ account_id: accountId, strategy_id: strategyId }),
  })
}

export function createWarmupSession(accountId: string, strategyId: string): Promise<WarmupSessionDetail> {
  return apiRequest('/api/warmup/sessions', {
    method: 'POST',
    body: JSON.stringify({ account_id: accountId, strategy_id: strategyId }),
  })
}

export function pauseWarmupSession(sessionId: string, reason: string): Promise<WarmupSessionDetail> {
  return apiRequest(`/api/warmup/sessions/${encodeURIComponent(sessionId)}/pause`, {
    method: 'PUT',
    body: JSON.stringify({ reason }),
  })
}

export function resumeWarmupSession(sessionId: string): Promise<WarmupSessionDetail> {
  return apiRequest(`/api/warmup/sessions/${encodeURIComponent(sessionId)}/resume`, {
    method: 'PUT',
  })
}

export function deleteWarmupSession(sessionId: string): Promise<void> {
  return apiRequest(`/api/warmup/sessions/${encodeURIComponent(sessionId)}`, {
    method: 'DELETE',
  })
}

export function fetchWarmupEvents(sessionId: string, params?: { page?: number; limit?: number }): Promise<WarmupEventPage> {
  const query = new URLSearchParams()
  if (params?.page != null) query.set('page', String(params.page))
  if (params?.limit != null) query.set('limit', String(params.limit))
  const qs = query.toString()
  return apiRequest(`/api/warmup/sessions/${encodeURIComponent(sessionId)}/events${qs ? `?${qs}` : ''}`)
}

export function fetchWarmupSessionDetail(sessionId: string): Promise<WarmupSessionDetail> {
  return apiRequest(`/api/warmup/sessions/${encodeURIComponent(sessionId)}`)
}

export function fetchWarmupIsolationStatus(accountId: string): Promise<WarmupIsolationStatus> {
  return apiRequest(`/api/warmup/isolation/by-account/${encodeURIComponent(accountId)}`)
}
