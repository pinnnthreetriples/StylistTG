import { apiRequest } from '@/lib/http'

import type {
  WarmupActionMetadata,
  WarmupActionPreset,
  WarmupCyclicCreatePayload,
  WarmupCyclicCreateResponse,
  WarmupEventPage,
  WarmupIsolationStatus,
  WarmupReadiness,
  WarmupSessionDetail,
  WarmupSessionPage,
  WarmupStrategy,
  WarmupSelectableAccount,
  WarmupSelectableAccountFilters,
  WarmupValidateResponse,
} from './types'

export function fetchWarmupReadiness(): Promise<WarmupReadiness> {
  return apiRequest('/api/warmup/readiness')
}

export function fetchWarmupStrategies(): Promise<WarmupStrategy[]> {
  return apiRequest('/api/warmup/strategies')
}

export function fetchWarmupActionMetadata(): Promise<WarmupActionMetadata[]> {
  return apiRequest('/api/warmup-actions/metadata')
}

export function applyWarmupActionPreset(strategyId: string, preset: WarmupActionPreset): Promise<WarmupStrategy> {
  return apiRequest(`/api/warmup/strategies/${encodeURIComponent(strategyId)}/apply-preset`, {
    method: 'POST',
    body: JSON.stringify({ preset }),
  })
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

export function createCyclicWarmupSessions(payload: WarmupCyclicCreatePayload): Promise<WarmupCyclicCreateResponse> {
  return apiRequest('/api/warmup-sessions/cyclic', {
    method: 'POST',
    body: JSON.stringify(payload),
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

export function updateWarmupDisabledActions(sessionId: string, actions: string[]): Promise<WarmupSessionDetail> {
  return apiRequest(`/api/warmup/sessions/${encodeURIComponent(sessionId)}/disabled-actions`, {
    method: 'PATCH',
    body: JSON.stringify({ actions }),
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

export function fetchWarmupSelectableAccounts(
  filters: WarmupSelectableAccountFilters = {},
): Promise<WarmupSelectableAccount[]> {
  const query = new URLSearchParams()
  if (filters.search) query.set('search', filters.search)
  if (filters.country) query.set('country', filters.country)
  if (filters.role) query.set('role', filters.role)
  if (filters.proxyOkOnly) query.set('proxy_ok_only', 'true')
  if (filters.hideInWork) query.set('hide_in_work', 'true')
  query.set('limit', '500')
  return apiRequest(`/api/warmup-selectable-accounts?${query.toString()}`)
}
