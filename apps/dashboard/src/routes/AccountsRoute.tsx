import { useNavigate } from '@tanstack/react-router'
import { useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'

import { AccountsPage } from '@/features/accounts/AccountsPage'
import { appRoutes } from '@/lib/routes'
import { accountsQueryOptions, accountRiskSummaryQueryOptions } from '@/lib/queries'

export function AccountsRoute() {
  const navigate = useNavigate()
  const accountsQuery = useQuery(accountsQueryOptions())
  const riskQuery = useQuery(accountRiskSummaryQueryOptions())
  const navigateToRoute = useCallback(
    (href: string) => {
      void navigate({ href })
    },
    [navigate],
  )

  const riskByAccount = new Map((riskQuery.data?.items ?? []).map((risk) => [risk.account_id, risk]))

  return (
    <AccountsPage
      accounts={accountsQuery.data ?? []}
      isLoading={accountsQuery.isLoading}
      onAddAccounts={() => navigateToRoute(appRoutes.accountAdd())}
      onSelectAccount={(accountId) => navigateToRoute(appRoutes.account(accountId))}
      riskByAccount={riskByAccount}
      riskSummary={riskQuery.data}
    />
  )
}
