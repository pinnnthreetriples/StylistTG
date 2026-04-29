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

export function readCachedDashboardHydration(
  storage: Pick<Storage, 'getItem'> | null,
  accountId: string,
): CachedDashboardHydration | null {
  const dashboard = readStoredDashboardCache(storage, accountId)
  if (!dashboard) {
    return null
  }

  const baselineForm = buildDashboardFormState(dashboard)
  return {
    dashboard,
    baselineForm,
    nextForm: readStoredDashboardFormDraft(storage, accountId) ?? baselineForm,
  }
}
