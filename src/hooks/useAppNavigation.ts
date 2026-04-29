import { useCallback, useEffect, useState, useTransition } from 'react'
import type React from 'react'

import { readAccountListView, writeAccountListView, type AccountListView } from '@/lib/appView'
import {
  resolvePopNavigationState,
  resolveTopLevelNavigationTarget,
  type AccountListTab,
  type NavigationState,
} from '@/lib/appNavigation'
import type { AuthPhase } from '@/lib/auth'

export function useAppNavigation({
  accountId,
  initialNavigation,
  setAuthPhase,
  skipNextAuthBootstrapRef,
}: {
  accountId: string | null
  initialNavigation: NavigationState
  setAuthPhase: React.Dispatch<React.SetStateAction<AuthPhase>>
  skipNextAuthBootstrapRef: React.MutableRefObject<boolean>
}) {
  const [accountListView, setAccountListView] = useState<AccountListTab>(initialNavigation.accountListView)
  const [, startNavigationTransition] = useTransition()

  useEffect(() => {
    function handlePopState() {
      const nextState = resolvePopNavigationState({
        hasAccountId: Boolean(accountId),
        nextView: readAccountListView(window.location.search),
      })
      if (!nextState) return
      skipNextAuthBootstrapRef.current = true
      setAuthPhase(nextState.phase)
      setAccountListView(nextState.accountListView)
    }

    window.addEventListener('popstate', handlePopState)
    return () => window.removeEventListener('popstate', handlePopState)
  }, [accountId, setAuthPhase, skipNextAuthBootstrapRef])

  const showTopLevelView = useCallback(
    (view: AccountListView, mode: 'push' | 'replace' = 'push') => {
      const nextState = resolveTopLevelNavigationTarget(view)
      skipNextAuthBootstrapRef.current = true
      writeAccountListView(view, mode)
      startNavigationTransition(() => {
        setAuthPhase(nextState.phase)
        setAccountListView(nextState.accountListView)
      })
    },
    [setAuthPhase, skipNextAuthBootstrapRef],
  )

  const transitionToPhase = useCallback((phase: AuthPhase) => {
    startNavigationTransition(() => setAuthPhase(phase))
  }, [setAuthPhase])

  return {
    accountListView,
    showTopLevelView,
    transitionToPhase,
  }
}
