import { Button, ProductEmptyState } from '@stylisttg/ui'

import type { WarmupSelectableAccount } from '../types'
import { AccountSelectorRow } from './AccountSelectorRow'

export function AvailableAccountsColumn({
  accounts,
  filteredCount,
  onAdd,
  onAddAll,
}: {
  accounts: WarmupSelectableAccount[]
  filteredCount: number
  onAdd: (accountId: string) => void
  onAddAll: () => void
}) {
  return (
    <section className="min-h-80 overflow-hidden rounded-lg border border-border bg-card">
      <div className="flex items-center justify-between gap-3 border-b border-border px-3 py-2">
        <div>
          <div className="text-sm font-semibold text-foreground">Доступные</div>
          <div className="text-xs text-muted-foreground">Отфильтровано: {filteredCount}</div>
        </div>
        <Button disabled={accounts.length === 0} type="button" variant="outline" onClick={onAddAll}>
          Добавить все
        </Button>
      </div>
      {accounts.length === 0 ? (
        <div className="p-4">
          <ProductEmptyState title="Нет аккаунтов, соответствующих фильтрам" description="Измените поиск, страну или proxy-фильтр." />
        </div>
      ) : (
        <div className="max-h-[34rem] overflow-auto">
          {accounts.map((account) => (
            <AccountSelectorRow account={account} direction="add" key={account.account_id} onMove={onAdd} />
          ))}
        </div>
      )}
    </section>
  )
}
