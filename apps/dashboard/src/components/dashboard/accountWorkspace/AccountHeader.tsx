import { RiskBadge, Badge, StatusPill, Button } from '@stylisttg/ui'
import { ArrowLeft, RefreshCw, CheckCircle, Plus } from 'lucide-react'

import { maskPhone } from '@/lib/accounts'
import { labelRiskLevelShort, labelRuntimeHealth, labelProxyStatus, runtimeHealthTone } from '@/lib/uiLabels'
import type { AccountRisk } from '@/features/accounts/accountRisk'

type HeaderAccount = {
  account_id: string
  display_name: string | null
  username: string | null
  phone_number: string | null
  account_state: string
  runtime_health: string
  is_execution_usable: boolean
}

export type AccountHeaderProps = {
  account: HeaderAccount
  risk?: AccountRisk | null
  proxyStatus?: string | null
  onCheck?: () => void
  onSync?: () => void
  onCreateJob?: () => void
  onBack?: () => void
  isChecking?: boolean
  isSyncing?: boolean
}

export function AccountHeader({
  account,
  risk,
  proxyStatus,
  onCheck,
  onSync,
  onCreateJob,
  onBack,
  isChecking,
  isSyncing,
}: AccountHeaderProps) {
  const isAuthorized = account.is_execution_usable || account.account_state === 'authorized_ready'
  const hasProblem = ['runtime_broken', 'reauth_required', 'manual_intervention_needed', 'disabled'].includes(account.account_state)
  const status = isAuthorized
    ? { label: 'Авторизован', kind: 'authorized' }
    : hasProblem
      ? { label: 'Требует внимания', kind: 'error' }
      : { label: 'Требует входа', kind: 'waiting' }
  const statusTone = status.kind === 'authorized' ? 'green' : status.kind === 'error' ? 'red' : 'amber'

  return (
    <div className="border-b border-border bg-card px-4 py-3 sm:px-6">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-4 gap-y-2">
        {onBack ? (
          <Button onClick={onBack} type="button" variant="ghost">
            <ArrowLeft className="size-4" />
            Назад
          </Button>
        ) : null}
        {/* Identity */}
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h1 className="truncate text-base font-bold text-foreground">
              {account.display_name || maskPhone(account.phone_number ?? '')}
            </h1>
            {account.username ? (
              <span className="truncate text-sm text-muted-foreground">@{account.username}</span>
            ) : null}
          </div>
          <div className="mt-0.5 text-xs text-muted-foreground">{maskPhone(account.phone_number ?? '')}</div>
        </div>

        {/* Status pills */}
        <div className="flex flex-wrap items-center gap-2">
          <StatusPill tone={statusTone}>{status.label}</StatusPill>
          <Badge tone={runtimeHealthTone(account.runtime_health)}>
            {labelRuntimeHealth(account.runtime_health)}
          </Badge>
          {risk ? (
            <RiskBadge
              label={labelRiskLevelShort(risk.level)}
              level={risk.level}
              score={risk.score}
            />
          ) : null}
          <span className="text-xs text-muted-foreground">{labelProxyStatus(proxyStatus ?? 'none')}</span>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2">
          {onCheck ? (
            <Button variant="secondary" onClick={onCheck} disabled={isChecking} type="button">
              <CheckCircle className="size-3.5" />
              {isChecking ? 'Проверка...' : 'Проверить'}
            </Button>
          ) : null}
          {onSync ? (
            <Button variant="secondary" onClick={onSync} disabled={isSyncing} type="button">
              <RefreshCw className={`size-3.5 ${isSyncing ? 'animate-spin' : ''}`} />
              {isSyncing ? 'Синхронизация...' : 'Синхронизировать'}
            </Button>
          ) : null}
          {onCreateJob ? (
            <Button onClick={onCreateJob} type="button">
              <Plus className="size-3.5" />
              Создать задачу
            </Button>
          ) : null}
        </div>
      </div>
    </div>
  )
}
