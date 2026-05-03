import { PageHeader, SectionCard } from '@stylisttg/ui'

import type { AccountRisk } from '@/features/accounts/accountRisk'
import { AccountsTable } from '@/features/accounts/AccountsTable'
import type { AccountListItem } from '@/lib/api'

export function AccountsPage({
  accounts,
  isLoading,
  onSelectAccount,
  riskByAccount,
}: {
  accounts: AccountListItem[]
  isLoading?: boolean
  onSelectAccount?: (accountId: string) => void
  riskByAccount?: Map<string, AccountRisk>
}) {
  return (
    <div className="grid gap-5">
      <PageHeader
        eyebrow="Accounts"
        title="Account Operations"
        description="Read-only SaaS table foundation for account inventory, filtering, selection, and future bulk actions."
      />
      <SectionCard title="Account inventory">
        <AccountsTable accounts={accounts} isLoading={isLoading} onSelectAccount={onSelectAccount} riskByAccount={riskByAccount} />
      </SectionCard>
    </div>
  )
}
