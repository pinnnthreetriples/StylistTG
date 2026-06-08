// fallow-ignore-file complexity
// fallow-ignore-reason: Form section renderer keeps wizard field layout colocated with validation copy.
import { Alert, Badge, Button, Select } from '@stylisttg/ui'
import { AlertTriangle, CalendarClock, CheckCircle2, PlayCircle, Search, ShieldCheck } from 'lucide-react'

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
      <WarmupProxyAdaptationNotice validation={validation} />
      {validation.blocking_reasons.length > 0 ? <Alert variant="error">{validation.blocking_reasons.join(', ')}</Alert> : null}
      {validation.warnings.length > 0 ? <Alert variant="warning">{validation.warnings.join(', ')}</Alert> : null}
    </div>
  )
}

function WarmupProxyAdaptationNotice({ validation }: { validation: WarmupValidateResponse }) {
  const adaptation = validation.proxy_adaptation
  if (!adaptation) return null
  const disabledActions = adaptation.disabled_actions
  const presetLabel = PROXY_PRESET_LABELS[adaptation.applied_preset] ?? adaptation.applied_preset
  const categoryLabel = PROXY_CATEGORY_LABELS[adaptation.proxy_category] ?? adaptation.proxy_category
  if (disabledActions.length === 0) {
    return (
      <Alert variant="info">
        Применён preset: {presetLabel} из-за {categoryLabel} proxy.
      </Alert>
    )
  }
  return (
    <Alert icon={<AlertTriangle className="size-4" />} variant="warning">
      Применён preset: {presetLabel} из-за {categoryLabel} proxy. Автоматически отключены:{' '}
      {disabledActions.map(formatActionType).join(', ')}.
    </Alert>
  )
}

export function WarmupCyclicConfig({
  daysTotal,
  enabled,
  endHour,
  onDaysTotalChange,
  onEnabledChange,
  onEndHourChange,
  onStartHourChange,
  startHour,
}: {
  daysTotal: number
  enabled: boolean
  endHour: number
  onDaysTotalChange: (value: number) => void
  onEnabledChange: (value: boolean) => void
  onEndHourChange: (value: number) => void
  onStartHourChange: (value: number) => void
  startHour: number
}) {
  const invalidWindow = enabled && startHour === endHour
  const activeHours = enabled ? computeActiveHours(startHour, endHour, daysTotal) : 0
  return (
    <div className="mt-5 rounded-lg border border-border bg-card px-3 py-3">
      <label className="flex items-center gap-2 text-sm font-semibold text-foreground">
        <input
          checked={enabled}
          className="size-4"
          type="checkbox"
          onChange={(event) => onEnabledChange(event.target.checked)}
        />
        <CalendarClock className="size-4 text-muted-foreground" />
        Циклический режим
      </label>
      {enabled ? (
        <div className="mt-3 grid gap-3 sm:grid-cols-3">
          <label className="grid gap-1.5">
            <span className="text-xs font-semibold uppercase text-muted-foreground">Начало</span>
            <input
              className="h-9 rounded-md border border-border px-3 text-sm"
              max={23}
              min={0}
              type="number"
              value={startHour}
              onChange={(event) => onStartHourChange(clampHour(event.target.value))}
            />
          </label>
          <label className="grid gap-1.5">
            <span className="text-xs font-semibold uppercase text-muted-foreground">Конец</span>
            <input
              className="h-9 rounded-md border border-border px-3 text-sm"
              max={23}
              min={0}
              type="number"
              value={endHour}
              onChange={(event) => onEndHourChange(clampHour(event.target.value))}
            />
          </label>
          <label className="grid gap-1.5">
            <span className="text-xs font-semibold uppercase text-muted-foreground">Дней</span>
            <input
              className="h-9 rounded-md border border-border px-3 text-sm"
              max={30}
              min={1}
              type="number"
              value={daysTotal}
              onChange={(event) => onDaysTotalChange(clampDays(event.target.value))}
            />
          </label>
          <div className="sm:col-span-3 text-xs text-muted-foreground">
            {invalidWindow
              ? 'Активное окно не может начинаться и заканчиваться в один час.'
              : `Ожидаются активные часы: ${formatHour(startHour)}-${formatHour(endHour)}, всего ${activeHours} ч.`}
          </div>
        </div>
      ) : null}
    </div>
  )
}

export function WarmupCreateSummary({
  canCreate,
  cycleConfig,
  isCreating,
  onCreate,
  selectedAccountId,
  selectedAccountLabel,
  selectedStrategy,
}: {
  canCreate: boolean
  cycleConfig: { startHour: number; endHour: number; daysTotal: number } | null
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
            ? cycleConfig
              ? `План: ${selectedStrategy.name}. Цикл ${formatHour(cycleConfig.startHour)}-${formatHour(cycleConfig.endHour)} на ${cycleConfig.daysTotal} дн.`
              : `План: ${selectedStrategy.name}. Создание сессии ставит аккаунт в ${selectedStrategy.duration_days}-дневное расписание dry-run.`
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

function clampHour(value: string): number {
  return Math.max(0, Math.min(23, Number.parseInt(value || '0', 10)))
}

function clampDays(value: string): number {
  return Math.max(1, Math.min(30, Number.parseInt(value || '1', 10)))
}

function computeActiveHours(startHour: number, endHour: number, daysTotal: number): number {
  if (startHour === endHour) return 0
  const hoursPerDay = startHour < endHour ? endHour - startHour : 24 - startHour + endHour
  return hoursPerDay * daysTotal
}

function formatHour(hour: number): string {
  return `${String(hour).padStart(2, '0')}:00`
}

const PROXY_PRESET_LABELS: Record<string, string> = {
  economic: 'economic',
  balanced: 'balanced',
  full: 'full',
}

const PROXY_CATEGORY_LABELS: Record<string, string> = {
  datacenter: 'datacenter',
  mobile: 'mobile',
  residential: 'residential',
  unknown: 'unknown',
}

function formatActionType(actionType: string): string {
  return actionType.replaceAll('_', ' ')
}
