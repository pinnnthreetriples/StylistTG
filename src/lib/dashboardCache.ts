import { fetchDashboard } from '@/lib/api'

export type DashboardState = Awaited<ReturnType<typeof fetchDashboard>>

const DASHBOARD_CACHE_KEY_PREFIX = 'stylisttg.dashboard.'

export function readStoredDashboardCache(
  storage: Pick<Storage, 'getItem'> | null,
  accountId: string | null,
): DashboardState | null {
  if (!storage || !accountId) {
    return null
  }
  try {
    const raw = storage.getItem(`${DASHBOARD_CACHE_KEY_PREFIX}${accountId}`)
    if (!raw) {
      return null
    }
    const parsed = JSON.parse(raw) as DashboardState
    return parsed.account?.account_id === accountId ? parsed : null
  } catch {
    return null
  }
}

export function persistDashboardCache(
  storage: Pick<Storage, 'setItem'> | null,
  accountId: string,
  dashboard: DashboardState,
): void {
  storage?.setItem(`${DASHBOARD_CACHE_KEY_PREFIX}${accountId}`, JSON.stringify(dashboard))
}

export function clearDashboardCache(storage: Pick<Storage, 'removeItem'> | null, accountId: string): void {
  storage?.removeItem(`${DASHBOARD_CACHE_KEY_PREFIX}${accountId}`)
}
