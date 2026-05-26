import { Button, Card, EmptyState, FormField, Input, Skeleton } from '@stylisttg/ui'
import { Trash2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'

import { buildCampaignAccountPayload, type AccountFormState } from '../formPayloads'
import { useAddCampaignAccount, useNeuroCampaignAccounts, useRemoveCampaignAccount } from '../hooks'
import type { NeuroCampaignAccountCreate } from '../types'
import { SafetyGateBanner } from '@/modules/shared/SafetyGateBanner'

export function AccountsSection({ campaignId }: { campaignId: string }) {
  const accountsQuery = useNeuroCampaignAccounts(campaignId)
  const addAccount = useAddCampaignAccount(campaignId)
  const removeAccount = useRemoveCampaignAccount(campaignId)
  const [form, setForm] = useState<AccountFormState>({
    accountId: '',
    rotationWeight: '1',
    rotationOrder: '0',
  })
  const [formError, setFormError] = useState<string | null>(null)
  const accounts = accountsQuery.data?.items ?? []

  if (accountsQuery.isError) {
    return <Card className="p-4 text-sm text-destructive">Не удалось загрузить данные</Card>
  }
  if (accountsQuery.isLoading) return <Skeleton className="h-20 w-full" />

  const isMutating = addAccount.isPending || removeAccount.isPending
  const mutationError = addAccount.isError || removeAccount.isError ? 'Не удалось сохранить изменения' : null

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setFormError(null)
    let payload: NeuroCampaignAccountCreate
    try {
      payload = buildCampaignAccountPayload(form)
    } catch {
      setFormError('Заполните account_id и корректные значения ротации')
      return
    }
    addAccount.mutate(payload, {
      onSuccess: () => {
        setForm({ accountId: '', rotationWeight: '1', rotationOrder: '0' })
      },
    })
  }

  return (
    <Card className="p-4">
      <h3 className="mb-3 text-sm font-semibold text-foreground">Аккаунты ({accountsQuery.data?.total ?? 0})</h3>
      <form className="mb-3 grid gap-2 sm:grid-cols-[1fr_80px_80px_auto]" onSubmit={handleSubmit}>
        <FormField className="sm:col-span-1" error={formError} htmlFor="neuro-account-id">
          <Input
            id="neuro-account-id"
            placeholder="account_id"
            value={form.accountId}
            onChange={(event) => setForm((current) => ({ ...current, accountId: event.target.value }))}
          />
        </FormField>
        <Input
          aria-label="rotation_weight"
          min={1}
          type="number"
          value={form.rotationWeight}
          onChange={(event) => setForm((current) => ({ ...current, rotationWeight: event.target.value }))}
        />
        <Input
          aria-label="rotation_order"
          min={0}
          type="number"
          value={form.rotationOrder}
          onChange={(event) => setForm((current) => ({ ...current, rotationOrder: event.target.value }))}
        />
        <Button type="submit" disabled={isMutating || !form.accountId.trim()}>
          Добавить
        </Button>
      </form>
      {mutationError ? <p className="mb-3 text-xs font-medium text-destructive">{mutationError}</p> : null}
      {accounts.length === 0 ? (
        <EmptyState title="Нет аккаунтов" description="Добавьте аккаунты к кампании" />
      ) : (
        <div className="space-y-1.5">
          {accounts.map((account) => (
            <div key={account.id} className="rounded border border-border px-3 py-2 text-sm">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <span className="font-medium text-foreground">{account.account_id}</span>
                  <span className="ml-2 text-xs text-muted-foreground">
                    w:{account.rotation_weight} o:{account.rotation_order}
                  </span>
                </div>
                <Button
                  size="sm"
                  variant="ghost"
                  icon={<Trash2 className="size-3.5" />}
                  onClick={() => removeAccount.mutate(account.account_id)}
                  disabled={isMutating}
                >
                  Удалить
                </Button>
              </div>
              <div className="mt-2">
                <SafetyGateBanner accountId={account.account_id} intent="commenting" />
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}
