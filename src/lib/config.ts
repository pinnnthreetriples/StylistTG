const DEFAULT_POLLING_INTERVAL_MS = 3000
const DEFAULT_REQUEST_TIMEOUT_MS = 15000

type FrontendEnv = Record<string, string | undefined>

const env = import.meta.env as FrontendEnv

export function getApiBaseUrl(): string {
  return env.VITE_API_BASE_URL ?? ''
}

export function getPollingIntervalMs(): number {
  return parsePositiveInteger(env.VITE_POLLING_INTERVAL_MS, DEFAULT_POLLING_INTERVAL_MS)
}

export function getRequestTimeoutMs(): number {
  return parsePositiveInteger(env.VITE_REQUEST_TIMEOUT_MS, DEFAULT_REQUEST_TIMEOUT_MS)
}

function parsePositiveInteger(value: string | undefined, fallback: number): number {
  if (!value) {
    return fallback
  }

  const parsed = Number.parseInt(value, 10)
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback
}
