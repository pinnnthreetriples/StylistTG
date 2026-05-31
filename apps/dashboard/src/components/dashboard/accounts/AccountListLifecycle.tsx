import { Loader2, Plus, Server, Trash2, UserRound, X } from 'lucide-react'
import { useState } from 'react'

import type { AccountDeletionPreview, AccountListItem } from '@/lib/api'
import {
  useAccountAuditEventsQuery,
  useAccountCooldownsQuery,
  useAccountDeletionPreviewQuery,
  useAccountDeletionRequestsQuery,
  useAccountExportRequestsQuery,
  useActionGateQuery,
  useCreateAccountDeletionRequestMutation,
  useCreateAccountExportRequestMutation,
} from '@/hooks/queries/useAccountsQueries'

export function EmptyAccounts({ onAddBatch }: { onAddBatch: () => void }) {
  return (
    <section className="rounded-xl border border-border bg-card p-8 text-center shadow-sm">
      <div className="mx-auto flex size-12 items-center justify-center rounded-xl bg-muted">
        <UserRound className="size-5 text-primary" />
      </div>
      <h1 className="mt-4 font-sans text-xl font-bold tracking-tight text-foreground">
        Аккаунтов пока нет
      </h1>
      <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-muted-foreground">
        Добавьте один или несколько Telegram-аккаунтов, чтобы открыть редактор профиля и запускать задачи.
      </p>
      <button
        className="mt-5 inline-flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground"
        onClick={onAddBatch}
        type="button"
      >
        <Plus className="size-4" />
        Добавить аккаунты
      </button>
    </section>
  )
}

export function DeleteAccountDialog({
  account,
  error,
  onCancel,
  onError,
  onSubmitted,
}: {
  account: AccountListItem
  error: string | null
  onCancel: () => void
  onError: (message: string | null) => void
  onSubmitted: () => void
}) {
  const name = account.display_name || account.phone_number
  const previewQuery = useAccountDeletionPreviewQuery(account.account_id)
  const deletionRequestsQuery = useAccountDeletionRequestsQuery(account.account_id)
  const exportRequestsQuery = useAccountExportRequestsQuery(account.account_id)
  const auditEventsQuery = useAccountAuditEventsQuery(account.account_id, 8)
  const cooldownsQuery = useAccountCooldownsQuery(account.account_id)
  const actionGateQuery = useActionGateQuery(account.account_id, 'account.delete')
  const deletionRequestMutation = useCreateAccountDeletionRequestMutation()
  const exportRequestMutation = useCreateAccountExportRequestMutation()
  const [reason, setReason] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const isSubmitting = deletionRequestMutation.isPending
  const preview = previewQuery.data
  const canSubmit =
    confirmation === 'DELETE' &&
    reason.trim().length >= 10 &&
    preview?.can_delete !== false &&
    !isSubmitting

  async function submitDeletionRequest() {
    onError(null)
    if (!canSubmit) return
    try {
      await deletionRequestMutation.mutateAsync({
        accountId: account.account_id,
        dryRun: true,
        reason: reason.trim(),
      })
      onSubmitted()
    } catch {
      onError('Не удалось создать заявку на удаление. Проверьте preview, reason и confirmation.')
    }
  }

  async function requestExport() {
    onError(null)
    try {
      await exportRequestMutation.mutateAsync(account.account_id)
    } catch {
      onError('Не удалось создать export request.')
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-foreground/20 px-4">
      <div className="max-h-[90vh] w-full max-w-2xl overflow-hidden rounded-2xl bg-card shadow-xl">
        <div className="flex items-center justify-between border-b border-border px-5 py-4">
          <div>
            <h2 className="font-sans text-base font-bold text-foreground">Account lifecycle request</h2>
            <p className="mt-0.5 text-xs text-muted-foreground">{name}</p>
          </div>
          <button
            aria-label="Закрыть подтверждение удаления"
            className="flex size-8 items-center justify-center rounded-lg text-muted-foreground hover:bg-muted hover:text-foreground"
            disabled={isSubmitting}
            onClick={onCancel}
            type="button"
          >
            <X className="size-4" />
          </button>
        </div>
        <div className="max-h-[68vh] overflow-y-auto px-5 py-4">
          <p className="text-sm leading-6 text-muted-foreground">
            Удаление теперь проходит через auditable lifecycle request. По умолчанию создаётся safe dry-run request:
            backend фиксирует preview, reason и audit event без live TDLib действий.
          </p>

          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <LifecycleCard title="Risk gate">
              <div className="text-xs text-muted-foreground">
                {actionGateQuery.data ? (
                  <>
                    <div className="font-semibold text-foreground">
                      {actionGateQuery.data.allowed ? 'Allowed' : 'Blocked'} · {actionGateQuery.data.risk_level} · {actionGateQuery.data.risk_score}
                    </div>
                    <div className="mt-1">{actionGateQuery.data.requires_override ? 'Override reason required.' : 'No override required for this request.'}</div>
                  </>
                ) : actionGateQuery.isError ? (
                  'Risk gate unavailable.'
                ) : (
                  'Checking risk gate...'
                )}
              </div>
            </LifecycleCard>
            <LifecycleCard title="Cooldowns">
              <CompactList
                empty="No active cooldowns."
                items={(cooldownsQuery.data ?? []).map((cooldown) => `${cooldown.operation}: ${cooldown.reason_code}`)}
                loading={cooldownsQuery.isPending}
              />
            </LifecycleCard>
          </div>

          <LifecycleCard className="mt-3" title="Deletion preview">
            {previewQuery.isPending ? (
              <div className="text-xs text-muted-foreground">Loading deletion preview...</div>
            ) : previewQuery.isError ? (
              <div className="text-xs font-semibold text-destructive">Deletion preview unavailable.</div>
            ) : preview ? (
              <DeletionPreview preview={preview} />
            ) : null}
          </LifecycleCard>

          <div className="mt-3 grid gap-3 md:grid-cols-2">
            <LifecycleCard title="Export data">
              <button
                className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-2 text-xs font-semibold text-foreground hover:bg-muted disabled:opacity-60"
                disabled={exportRequestMutation.isPending}
                onClick={() => void requestExport()}
                type="button"
              >
                {exportRequestMutation.isPending ? <Loader2 className="size-3.5 animate-spin" /> : <Server className="size-3.5" />}
                Request export
              </button>
              <CompactList
                empty="No export requests yet."
                items={(exportRequestsQuery.data ?? []).slice(0, 3).map((item) => `${item.status} · ${formatLifecycleTime(item.requested_at)}`)}
                loading={exportRequestsQuery.isPending}
              />
            </LifecycleCard>
            <LifecycleCard title="Audit history">
              <CompactList
                empty="No audit events yet."
                items={(auditEventsQuery.data?.items ?? []).slice(0, 4).map((item) => `${item.action} · ${formatLifecycleTime(item.created_at)}`)}
                loading={auditEventsQuery.isPending}
              />
            </LifecycleCard>
          </div>

          <LifecycleCard className="mt-3" title="Deletion request">
            <label className="grid gap-1 text-xs font-semibold text-muted-foreground">
              Reason
              <textarea
                aria-label="Deletion reason"
                className="min-h-20 rounded-lg border border-border px-3 py-2 text-sm font-normal text-foreground outline-none focus:border-border"
                onChange={(event) => setReason(event.target.value)}
                placeholder="Describe why this account lifecycle request is required..."
                value={reason}
              />
            </label>
            <label className="mt-3 grid gap-1 text-xs font-semibold text-muted-foreground">
              Confirmation
              <input
                aria-label="Deletion confirmation"
                className="rounded-lg border border-border px-3 py-2 text-sm font-normal text-foreground outline-none focus:border-border"
                onChange={(event) => setConfirmation(event.target.value)}
                placeholder="Type DELETE"
                value={confirmation}
              />
            </label>
            <CompactList
              empty="No deletion requests yet."
              items={(deletionRequestsQuery.data ?? []).slice(0, 3).map((item) => `${item.status} · ${formatLifecycleTime(item.requested_at)}`)}
              loading={deletionRequestsQuery.isPending}
            />
          </LifecycleCard>

          {error ? (
            <div className="mt-3 rounded-lg border border-destructive/20 bg-destructive/10 px-3 py-2 text-xs font-medium text-destructive">
              {error}
            </div>
          ) : null}
        </div>
        <div className="flex items-center justify-end gap-2 bg-muted px-5 py-4">
          <button
            className="rounded-lg px-3.5 py-2 text-sm font-medium text-muted-foreground hover:bg-muted hover:text-foreground"
            disabled={isSubmitting}
            onClick={onCancel}
            type="button"
          >
            Отмена
          </button>
          <button
            className="inline-flex items-center gap-1.5 rounded-lg bg-destructive px-3.5 py-2 text-sm font-semibold text-primary-foreground transition-all hover:bg-destructive disabled:opacity-60"
            disabled={!canSubmit}
            onClick={() => void submitDeletionRequest()}
            type="button"
          >
            {isSubmitting ? <Loader2 className="size-4 animate-spin" /> : <Trash2 className="size-4" />}
            Create request
          </button>
        </div>
      </div>
    </div>
  )
}

function LifecycleCard({
  children,
  className = '',
  title,
}: {
  children: React.ReactNode
  className?: string
  title: string
}) {
  return (
    <section className={`rounded-xl border border-border bg-muted p-3 ${className}`}>
      <h3 className="text-xs font-bold uppercase tracking-wide text-muted-foreground">{title}</h3>
      <div className="mt-2">{children}</div>
    </section>
  )
}

function CompactList({ empty, items, loading }: { empty: string; items: string[]; loading: boolean }) {
  if (loading) return <div className="mt-2 text-xs text-muted-foreground">Loading...</div>
  if (items.length === 0) return <div className="mt-2 text-xs text-muted-foreground">{empty}</div>
  return (
    <ul className="mt-2 grid gap-1 text-xs text-muted-foreground">
      {items.map((item) => (
        <li className="truncate rounded-lg bg-card px-2 py-1" key={item}>
          {item}
        </li>
      ))}
    </ul>
  )
}

function DeletionPreview({ preview }: { preview: AccountDeletionPreview }) {
  return (
    <div className="text-xs text-muted-foreground">
      <div className={`font-semibold ${preview.can_delete ? 'text-primary' : 'text-destructive'}`}>
        {preview.can_delete ? 'Request can be created' : 'Blocked'} · risk {preview.risk_level}
      </div>
      {preview.blocking_reasons.length > 0 ? (
        <ul className="mt-2 grid gap-1 text-destructive">
          {preview.blocking_reasons.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      ) : null}
      <div className="mt-2 grid gap-1">
        {preview.planned_actions.map((action, index) => (
          <div className="rounded-lg bg-card px-2 py-1" key={`${action.type}-${action.resource}-${index}`}>
            {action.resource}: {plannedActionDetail(action)}
          </div>
        ))}
      </div>
    </div>
  )
}

function plannedActionDetail(action: AccountDeletionPreview['planned_actions'][number]): string {
  if (typeof action.count === 'number') return `${action.count} item(s)`
  if (typeof action.present === 'boolean') return action.present ? 'present' : 'not present'
  return action.retention_policy ?? 'planned'
}

function formatLifecycleTime(value: string): string {
  const timestamp = Date.parse(value)
  if (!Number.isFinite(timestamp)) return value
  return new Date(timestamp).toLocaleString()
}
