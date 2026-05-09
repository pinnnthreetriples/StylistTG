import { useQuery } from '@tanstack/react-query'
import { Alert, Badge, Button, Select, SectionCard } from '@stylisttg/ui'
import { AlertTriangle, CheckCircle2, PlayCircle, Search, ShieldCheck } from 'lucide-react'
import { useMemo, useState } from 'react'

import { fetchAccounts } from '@/lib/api'
import { isApiError } from '@/lib/http'
import { queryKeys } from '@/lib/queries'

import { useCreateWarmupSession, useWarmupStrategies, useWarmupValidate } from '../hooks'
import {
  WARMUP_PRESET_LABELS,
  WARMUP_RISK_LEVEL_LABELS,
  WARMUP_RISK_TONES,
} from '../labels'
import type { WarmupStrategy } from '../types'

const EMPTY_ACCOUNTS: Awaited<ReturnType<typeof fetchAccounts>> = []
const EMPTY_STRATEGIES: WarmupStrategy[] = []

function describeStrategy(strategy: WarmupStrategy): string {
  const summaryAudience = strategy.ui_summary.audience_hint?.trim()
  if (summaryAudience) return summaryAudience
  if (strategy.description?.trim()) return strategy.description
  return 'План определяет темп подготовки, паузы и правила остановки при предупреждениях.'
}

export function WarmupCreateWizard() {
  const accountsQuery = useQuery({ queryKey: queryKeys.accounts, queryFn: fetchAccounts })
  const strategiesQuery = useWarmupStrategies()
  const validateMutation = useWarmupValidate()
  const createMutation = useCreateWarmupSession()
  const [accountId, setAccountId] = useState('')
  const [strategyId, setStrategyId] = useState('')
  const [validatedFor, setValidatedFor] = useState<string | null>(null)

  const accounts = accountsQuery.data ?? EMPTY_ACCOUNTS
  const strategies = strategiesQuery.data ?? EMPTY_STRATEGIES
  const defaultStrategy =
    strategies.find((strategy) => strategy.preset_kind === 'standard') ??
    strategies.find((strategy) => strategy.name.toLowerCase().includes('стандарт')) ??
    strategies[0]
  const selectedAccountId = accountId || accounts[0]?.account_id || ''
  const selectedStrategyId = strategyId || defaultStrategy?.id || ''
  const selectedStrategy = strategies.find((strategy) => strategy.id === selectedStrategyId)
  const canValidate = Boolean(selectedAccountId && selectedStrategyId)
  const validation = validateMutation.data
  const selectionKey = `${selectedAccountId}:${selectedStrategyId}`
  const validationMatchesSelection = validatedFor === selectionKey
  const canCreate = Boolean(validation?.is_ready && validationMatchesSelection && selectedAccountId && selectedStrategyId)
  const createErrorMessage =
    createMutation.error && isApiError(createMutation.error)
      ? createMutation.error.error_code === 'WARMUP_QUEUE_UNAVAILABLE'
        ? 'Сессию не удалось поставить в очередь задач. Запустите Redis/RQ worker или отключите live-выполнение подготовки.'
        : createMutation.error.message
      : 'Не удалось создать сессию. Проверьте готовность аккаунта.'

  const selectedAccountLabel = useMemo(() => {
    const account = accounts.find((item) => item.account_id === selectedAccountId)
    return account?.display_name || account?.phone_number || selectedAccountId
  }, [selectedAccountId, accounts])

  return (
    <SectionCard
      title="Создать сессию подготовки"
      description="Сначала проверяем готовность. После создания аккаунт не выполняет live-действия: модуль только ведёт расписание и аудит."
    >
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_auto]">
        <label className="grid gap-1.5">
          <span className="text-xs font-semibold uppercase text-gray-500">Аккаунт</span>
          <Select
            value={selectedAccountId}
            disabled={accounts.length === 0}
            onChange={(event) => {
              setAccountId(event.target.value)
              setValidatedFor(null)
              createMutation.reset()
            }}
          >
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
          <Button
            className="w-full min-w-32"
            disabled={!canValidate || validateMutation.isPending}
            type="button"
            variant="outline"
            onClick={() =>
              validateMutation.mutate(
                { accountId: selectedAccountId, strategyId: selectedStrategyId },
                { onSuccess: () => setValidatedFor(selectionKey) },
              )
            }
          >
            <Search className="size-4" />
            Проверить
          </Button>
        </div>
      </div>

      <div className="mt-5 grid gap-2">
        <div>
          <div className="text-xs font-semibold uppercase text-gray-500">Стратегия подготовки</div>
          <p className="mt-1 text-sm text-gray-600">
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
                    ? 'border-navy-300 bg-navy-50/60 text-navy-900 ring-1 ring-navy-100'
                    : 'border-gray-200 bg-white text-gray-900 hover:border-gray-300 hover:bg-gray-50'
                }`}
                key={strategy.id}
                type="button"
                onClick={() => {
                  setStrategyId(strategy.id)
                  setValidatedFor(null)
                  createMutation.reset()
                }}
              >
                <div className="flex items-center gap-2">
                  <ShieldCheck className={`size-4 ${selected ? 'text-navy-500' : 'text-gray-500'}`} />
                  <span className="text-sm font-semibold">{strategy.name}</span>
                </div>
                <div className="mt-2 flex flex-wrap items-center gap-1.5">
                  <Badge tone={selected ? 'blue' : 'gray'}>{presetLabel}</Badge>
                  <Badge tone="gray">{strategy.duration_days} дн.</Badge>
                  {riskLabel && riskTone ? <Badge tone={riskTone}>{riskLabel}</Badge> : null}
                </div>
                <p className="mt-2 text-xs leading-5 text-gray-600">
                  {describeStrategy(strategy)}
                </p>
                {speedHint ? (
                  <p className="mt-1 text-xs italic leading-5 text-gray-500">{speedHint}</p>
                ) : null}
              </button>
            )
          })}
        </div>
      </div>

      {validation ? (
        <div className="mt-5 grid gap-2">
          {validation.checks.map((check) => (
            <div
              className={`flex items-start justify-between gap-3 rounded-lg border px-3 py-2 ${
                check.passed ? 'border-emerald-100 bg-emerald-50/60' : 'border-amber-100 bg-amber-50/70'
              }`}
              key={check.key}
            >
              <div className="flex min-w-0 gap-2">
                {check.passed ? (
                  <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-emerald-600" />
                ) : (
                  <AlertTriangle className="mt-0.5 size-4 shrink-0 text-amber-600" />
                )}
                <div>
                <div className="text-sm font-semibold text-navy-900">{check.label}</div>
                {check.detail ? <div className="text-xs text-gray-500">{check.detail}</div> : null}
                </div>
              </div>
              <span className={check.passed ? 'text-sm font-semibold text-emerald-700' : 'text-sm font-semibold text-amber-700'}>
                {check.passed ? 'ОК' : check.severity === 'warning' ? 'Предупреждение' : 'Блокер'}
              </span>
            </div>
          ))}
          {validation.blocking_reasons.length > 0 ? (
            <Alert variant="error">{validation.blocking_reasons.join(', ')}</Alert>
          ) : null}
          {validation.warnings.length > 0 ? <Alert variant="warning">{validation.warnings.join(', ')}</Alert> : null}
        </div>
      ) : null}

      <div className="mt-5 rounded-lg border border-gray-200 bg-gray-50 px-3 py-3 text-sm text-gray-600">
        <div className="font-semibold text-navy-900">Что делает модуль сейчас</div>
        <p className="mt-1">
          В текущем режиме он не выполняет действий в Telegram. Он создаёт 14-дневный план, проверяет готовность аккаунта,
          показывает ближайший шаг, ставит ручную или системную паузу и пишет журнал событий.
        </p>
      </div>

      <div className="mt-5 flex flex-col gap-3 border-t border-gray-100 pt-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="text-sm font-semibold text-navy-900">
            {selectedAccountId ? `Выбран: ${selectedAccountLabel}` : 'Сначала добавьте аккаунт'}
          </div>
          <p className="mt-1 text-xs text-gray-500">
            {selectedStrategy
              ? `План: ${selectedStrategy.name}. Создание сессии ставит аккаунт в ${selectedStrategy.duration_days}-дневное расписание dry-run.`
              : 'Выберите понятный план подготовки, затем запустите проверку готовности.'}
          </p>
        </div>
        <Button
          className="min-w-40"
          disabled={!canCreate || createMutation.isPending}
          type="button"
          variant="outline"
          onClick={() =>
            createMutation.mutate(
              { accountId: selectedAccountId, strategyId: selectedStrategyId },
              {
                onSuccess: () => {
                  setAccountId('')
                  setStrategyId('')
                  setValidatedFor(null)
                  validateMutation.reset()
                },
              },
            )
          }
        >
          <PlayCircle className="size-4" />
          Создать сессию
        </Button>
      </div>
      {createMutation.error ? (
        <Alert className="mt-3" variant="error">
          {createErrorMessage}
        </Alert>
      ) : null}
    </SectionCard>
  )
}
