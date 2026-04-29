import { useNavigate } from '@tanstack/react-router'
import { useCallback } from 'react'

import { AccountList } from '@/components/dashboard/accounts/AccountList'
import { appRoutes } from '@/lib/routes'

export function AccountsRoute() {
  return <AccountsArea activeTab="accounts" />
}

export function SettingsRoute() {
  return <AccountsArea activeTab="settings" />
}

function AccountsArea({ activeTab }: { activeTab: 'accounts' | 'settings' }) {
  const navigate = useNavigate()
  const navigateToRoute = useCallback(
    (href: string) => {
      void navigate({ href })
    },
    [navigate],
  )

  return (
    <AccountList
      activeTab={activeTab}
      onAddBatch={() => navigateToRoute(appRoutes.authBatch())}
      onSelectAccount={(accountId) => navigateToRoute(appRoutes.account(accountId))}
      onTabChange={(tab) => navigateToRoute(tab === 'settings' ? appRoutes.settings() : appRoutes.accounts())}
    />
  )
}
