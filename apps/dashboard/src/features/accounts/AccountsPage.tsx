import { PageHeader, SectionCard } from '@stylisttg/ui'

import { AccountsTable } from '@/features/accounts/AccountsTable'
import type { AccountListItem } from '@/lib/api'

export function AccountsPage({
  accounts,
  isLoading,
  onSelectAccount,
}: {
  accounts: AccountListItem[]
  isLoading?: boolean
  onSelectAccount?: (accountId: string) => void
}) {
  return (
    <div className="grid gap-5">
      <PageHeader
        eyebrow="Accounts"
        title="Account Operations"
        description="Read-only SaaS table foundation for account inventory, filtering, selection, and future bulk actions."
      />
      <SectionCard title="Account inventory">
        <AccountsTable accounts={accounts} isLoading={isLoading} onSelectAccount={onSelectAccount} />
      </SectionCard>
    </div>
  )
}
