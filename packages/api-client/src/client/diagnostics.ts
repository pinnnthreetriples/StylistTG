import { unwrap } from './core'
import type { FrontendDiagnosticsSummary, LivePreflight, Readiness, RuntimeDiagnostics, StylistTgClient } from './types'
export async function fetchHealth(client: StylistTgClient): Promise<{ status: string }> {
  return client.request<{ status: string }>('/health')
}

export async function fetchReady(client: StylistTgClient): Promise<Readiness> {
  return client.request<Readiness>('/ready')
}

export async function fetchRuntimeDiagnostics(client: StylistTgClient): Promise<RuntimeDiagnostics> {
  return unwrap(client.openapi.GET('/diagnostics/runtime'), 'diagnostics')
}

export async function fetchLivePreflight(client: StylistTgClient): Promise<LivePreflight> {
  return unwrap(client.openapi.GET('/diagnostics/live-preflight'), 'live preflight')
}

export async function fetchFrontendDiagnosticsSummary(client: StylistTgClient): Promise<FrontendDiagnosticsSummary> {
  return unwrap(client.openapi.GET('/diagnostics/frontend-summary'), 'frontend diagnostics')
}
