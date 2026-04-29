import { useMemo } from 'react'

import { readStoredAccountId, resolveInitialAccountId } from '@/lib/auth'
import { shouldIgnoreStoredAccountForView } from '@/lib/appView'
import { readStoredDashboardCache } from '@/lib/dashboardCache'
import { buildDashboardFormState, type FormState } from '@/lib/dashboard'

export const emptyDashboardForm: FormState = {
  firstName: '',
  lastName: '',
  bio: '',
  username: '',
  profilePhotoAssetId: null,
  profileAudioAction: 'keep',
  profileAudioAssetId: null,
  stories: [],
}

export function useDashboardInitialState() {
  const initialAccountId = useMemo(
    () =>
      resolveInitialAccountId(
        window.location.search,
        shouldIgnoreStoredAccountForView(window.location.search) ? null : readStoredAccountId(window.localStorage),
        undefined,
      ),
    [],
  )
  const initialDashboard = useMemo(
    () => readStoredDashboardCache(window.localStorage, initialAccountId),
    [initialAccountId],
  )
  const initialForm = useMemo(
    () => (initialDashboard ? buildDashboardFormState(initialDashboard) : emptyDashboardForm),
    [initialDashboard],
  )

  return { initialAccountId, initialDashboard, initialForm }
}
