import { useMemo } from 'react'
import type { QueryClient } from '@tanstack/react-query'

import { readStoredDashboardCache } from '@/lib/dashboardCache'
import { type FormState } from '@/lib/dashboard'
import { getCachedDashboardBundle } from '@/lib/queries'
import { buildDashboardHydration } from '@/lib/dashboardNavigation'

export const emptyDashboardForm: FormState = {
  firstName: '',
  lastName: '',
  bio: '',
  username: '',
  profilePhotoAssetId: null,
  pinnedChannelRef: null,
  profileAudioAction: 'keep',
  profileAudioAssetId: null,
  stories: [],
}

export function useDashboardInitialState(routeAccountId: string | null, queryClient: QueryClient) {
  const initialAccountId = routeAccountId
  const initialBundle = useMemo(
    () => (initialAccountId ? getCachedDashboardBundle(queryClient, initialAccountId) ?? null : null),
    [initialAccountId, queryClient],
  )
  const initialDashboard = useMemo(
    () =>
      initialAccountId
        ? initialBundle?.dashboard ?? readStoredDashboardCache(window.localStorage, initialAccountId)
        : null,
    [initialAccountId, initialBundle],
  )
  const initialForm = useMemo(
    () =>
      initialAccountId && initialDashboard
        ? buildDashboardHydration(window.localStorage, initialAccountId, initialDashboard).nextForm
        : emptyDashboardForm,
    [initialAccountId, initialDashboard],
  )

  return { initialAccountId, initialBundle, initialDashboard, initialForm }
}
