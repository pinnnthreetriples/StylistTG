// fallow-ignore-file complexity
import { Alert, Badge, Button, Select } from '@stylisttg/ui'
import { AlertTriangle, CheckCircle2, PlayCircle, Search, ShieldCheck } from 'lucide-react'

import type { fetchAccounts } from '@/lib/api'

import {
  WARMUP_PRESET_LABELS,
  WARMUP_RISK_LEVEL_LABELS,
  WARMUP_RISK_TONES,
} from '../labels'
import type { WarmupStrategy, WarmupValidateResponse } from '../types'

type Account = Awaited<ReturnType<typeof fetchAccounts>>[number]

function describeStrategy(strategy: WarmupStrategy): string {
  const summaryAudience = strategy.ui_summary.audience_hint?.trim()
  if (summaryAudience) return summaryAudience
  if (strategy.description?.trim()) return strategy.description
  return 'План определяет темп подготовки, паузы и правила остановки при предупреждениях.'
}

export function WarmupAccountSelector({
  accounts,
  canValidate,
  isValidating,
  onAccountChange,
  onValidate,
  selectedAccountId,
}: {
  accounts: Account[]
  canValidate: boolean
  isValidating: boolean
  onAccountChange: (accountId: string) => void
  onValidate: () => void
  selectedAccountId: string
}) {
  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_auto]">
      <label className="grid gap-1.5">
        <span className="text-xs font-semibold uppercase text-muted-foreground">Аккаунт</span>
        <Select value={selectedAccountId} disabled={accounts.length === 0} onChange={(event) => onAccountChange(event.target.value)}>
          {accounts.length > 0 ? (
            accounts.map((account) => (
              <option key={account.account_id} value={account.account_id}>
                {account.display_name || account.phone_number}
              </option>
            ))
          ) : (
            <option value="">Нет доступных аккаунтов</option>
          )}
        </Select>
      </label>
      <div className="flex items-end">
        <Button className="w-full min-w-32" disabled={!canValidate || isValidating} type="button" variant="outline" onClick={onValidate}>
          <Search className="size-4" />
          Проверить
        </Button>
      </div>
    </div>
  )
}

export function WarmupStrategySelector({
  onStrategyChange,
  selectedStrategyId,
  strategies,
}: {
  onStrategyChange: (strategyId: string) => void
  selectedStrategyId: string
  strategies: WarmupStrategy[]
}) {
  return (
    <div className="mt-5 grid gap-2">
      <div>
        <div className="text-xs font-semibold uppercase text-muted-foreground">Стратегия подготовки</div>
        <p className="mt-1 text-sm text-muted-foreground">
          Стратегия задаёт длительность плана и темп подготовки. Сама по себе она не запускает действия в Telegram.
        </p>
      </div>
      <div className="grid gap-3 md:grid-cols-3">
        {strategies.map((strategy) => {
          const selected = strategy.id === selectedStrategyId
          const presetLabel = WARMUP_PRESET_LABELS[strategy.preset_kind] ?? strategy.preset_kind
          const riskLevel = strategy.ui_summary.risk_level
          const riskLabel = riskLevel ? WARMUP_RISK_LEVEL_LABELS[riskLevel] : null
          const riskTone = riskLevel ? WARMUP_RISK_TONES[riskLevel] : null
          const speedHint = strategy.ui_summary.speed_hint?.trim()
          return (
            <button
              className={`rounded-lg border p-3 text-left transition ${
                selected
                  ? 'border-border bg-muted text-foreground ring-1 ring-ring'
                  : 'border-border bg-card text-foreground hover:border-border hover:bg-muted'
              }`}
              key={strategy.id}
              type="button"
              onClick={() => onStrategyChange(strategy.id)}
            >
              <div className="flex items-center gap-2">
                <ShieldCheck className={`size-4 ${selected ? 'text-primary' : 'text-muted-foreground'}`} />
                <span className="text-sm font-semibold">{strategy.name}</span>
              </div>
              <div className="mt-2 flex flex-wrap items-center gap-1.5">
                <Badge tone={selected ? 'blue' : 'gray'}>{presetLabel}</Badge>
                <Badge tone="gray">{strategy.duration_days} дн.</Badge>
                {riskLabel && riskTone ? <Badge tone={riskTone}>{riskLabel}</Badge> : null}
              </div>
              <p className="mt-2 text-xs leading-5 text-muted-foreground">{describeStrategy(strategy)}</p>
              {speedHint ? <p className="mt-1 text-xs italic leading-5 text-muted-foreground">{speedHint}</p> : null}
            </button>
          )
        })}
      </div>
    </div>
  )
}

export function WarmupValidationPanel({ validation }: { validation: WarmupValidateResponse | undefined }) {
  if (!validation) return null

  return (
    <div className="mt-5 grid gap-2">
      {validation.checks.map((check) => (
        <div
          className={`flex items-start justify-between gap-3 rounded-lg border px-3 py-2 ${
            check.passed ? 'border-border bg-muted' : 'border-border bg-muted'
          }`}
          key={check.key}
        >
          <div className="flex min-w-0 gap-2">
            {check.passed ? (
              <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-primary" />
            ) : (
              <AlertTriangle className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
            )}
            <div>
              <div className="text-sm font-semibold text-foreground">{check.label}</div>
              {check.detail ? <div className="text-xs text-muted-foreground">{check.detail}</div> : null}
            </div>
          </div>
          <span className={check.passed ? 'text-sm font-semibold text-primary' : 'text-sm font-semibold text-muted-foreground'}>
            {check.passed ? 'ОК' : check.severity === 'warning' ? 'Предупреждение' : 'Блокер'}
          </span>
        </div>
      ))}
      {validation.blocking_reasons.length > 0 ? <Alert variant="error">{validation.blocking_reasons.join(', ')}</Alert> : null}
      {validation.warnings.length > 0 ? <Alert variant="warning">{validation.warnings.join(', ')}</Alert> : null}
    </div>
  )
}

export function WarmupCreateSummary({
  canCreate,
  isCreating,
  onCreate,
  selectedAccountId,
  selectedAccountLabel,
  selectedStrategy,
}: {
  canCreate: boolean
  isCreating: boolean
  onCreate: () => void
  selectedAccountId: string
  selectedAccountLabel: string
  selectedStrategy: WarmupStrategy | undefined
}) {
  return (
    <div className="mt-5 flex flex-col gap-3 border-t border-border pt-4 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <div className="text-sm font-semibold text-foreground">
          {selectedAccountId ? `Выбран: ${selectedAccountLabel}` : 'Сначала добавьте аккаунт'}
        </div>
        <p className="mt-1 text-xs text-muted-foreground">
          {selectedStrategy
            ? `План: ${selectedStrategy.name}. Создание сессии ставит аккаунт в ${selectedStrategy.duration_days}-дневное расписание dry-run.`
            : 'Выберите понятный план подготовки, затем запустите проверку готовности.'}
        </p>
      </div>
      <Button className="min-w-40" disabled={!canCreate || isCreating} type="button" variant="outline" onClick={onCreate}>
        <PlayCircle className="size-4" />
        Создать сессию
      </Button>
    </div>
  )
}
