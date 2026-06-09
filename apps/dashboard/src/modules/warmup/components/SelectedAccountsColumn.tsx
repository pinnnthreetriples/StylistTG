import { Button, ProductEmptyState } from '@stylisttg/ui'

import type { WarmupSelectableAccount } from '../types'
import { groupSelectedAccounts } from './AccountSelectorModel'
import { AccountSelectorRow } from './AccountSelectorRow'

export function SelectedAccountsColumn({
  accounts,
  onRemove,
  onRemoveAll,
}: {
  accounts: WarmupSelectableAccount[]
  onRemove: (accountId: string) => void
  onRemoveAll: () => void
}) {
  const grouped = groupSelectedAccounts(accounts)
  const countries = Object.keys(grouped).sort()
  return (
    <section className="min-h-80 overflow-hidden rounded-lg border border-border bg-card">
      <div className="flex items-center justify-between gap-3 border-b border-border px-3 py-2">
        <div>
          <div className="text-sm font-semibold text-foreground">Выбранные</div>
          <div className="text-xs text-muted-foreground">Всего: {accounts.length}</div>
        </div>
        <Button disabled={accounts.length === 0} type="button" variant="outline" onClick={onRemoveAll}>
          Удалить все
        </Button>
      </div>
      {accounts.length === 0 ? (
        <div className="p-4">
          <ProductEmptyState title="Аккаунты ещё не выбраны" description="Добавьте один или несколько аккаунтов из левой колонки." />
        </div>
      ) : (
        <div className="max-h-[34rem] overflow-auto">
          {countries.map((country) => (
            <div key={country}>
              <div className="sticky top-0 z-10 border-b border-border bg-muted px-3 py-1.5 text-xs font-semibold uppercase text-muted-foreground">
                {country} · {grouped[country].length}
              </div>
              {grouped[country].map((account) => (
                <AccountSelectorRow account={account} direction="remove" key={account.account_id} onMove={onRemove} />
              ))}
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
