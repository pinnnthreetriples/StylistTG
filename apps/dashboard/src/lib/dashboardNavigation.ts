import {
  buildDashboardFormState,
  readStoredDashboardFormDraft,
  type FormState,
} from '@/lib/dashboard'
import { readStoredDashboardCache, type DashboardState } from '@/lib/dashboardCache'

export type CachedDashboardHydration = {
  dashboard: DashboardState
  baselineForm: FormState
  nextForm: FormState
}

export function buildDashboardHydration(
  storage: Pick<Storage, 'getItem'> | null,
  accountId: string,
  dashboard: DashboardState,
): CachedDashboardHydration {
  const baselineForm = buildDashboardFormState(dashboard)
  return {
    dashboard,
    baselineForm,
    nextForm: readStoredDashboardFormDraft(storage, accountId) ?? baselineForm,
  }
}

export function readCachedDashboardHydration(
  storage: Pick<Storage, 'getItem'> | null,
  accountId: string,
): CachedDashboardHydration | null {
  const dashboard = readStoredDashboardCache(storage, accountId)
  if (!dashboard) {
    return null
  }

  return buildDashboardHydration(storage, accountId, dashboard)
}
