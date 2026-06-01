// fallow-ignore-file complexity
import { useQuery } from '@tanstack/react-query'
import { Alert, SectionCard } from '@stylisttg/ui'
import { useMemo, useState } from 'react'

import { fetchAccounts } from '@/lib/api'
import { isApiError } from '@/lib/http'
import { queryKeys } from '@/lib/queries'

import { useCreateWarmupSession, useWarmupStrategies, useWarmupValidate } from '../hooks'
import type { WarmupStrategy } from '../types'
import {
  WarmupAccountSelector,
  WarmupCreateSummary,
  WarmupStrategySelector,
  WarmupValidationPanel,
} from './WarmupCreateWizardSections'

const EMPTY_ACCOUNTS: Awaited<ReturnType<typeof fetchAccounts>> = []
const EMPTY_STRATEGIES: WarmupStrategy[] = []

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
      <WarmupAccountSelector
        accounts={accounts}
        canValidate={canValidate}
        isValidating={validateMutation.isPending}
        selectedAccountId={selectedAccountId}
        onAccountChange={(nextAccountId) => {
          setAccountId(nextAccountId)
          setValidatedFor(null)
          createMutation.reset()
        }}
        onValidate={() =>
          validateMutation.mutate(
            { accountId: selectedAccountId, strategyId: selectedStrategyId },
            { onSuccess: () => setValidatedFor(selectionKey) },
          )
        }
      />
      <WarmupStrategySelector
        selectedStrategyId={selectedStrategyId}
        strategies={strategies}
        onStrategyChange={(nextStrategyId) => {
          setStrategyId(nextStrategyId)
          setValidatedFor(null)
          createMutation.reset()
        }}
      />
      <WarmupValidationPanel validation={validation} />

      <div className="mt-5 rounded-lg border border-border bg-muted px-3 py-3 text-sm text-muted-foreground">
        <div className="font-semibold text-foreground">Что делает модуль сейчас</div>
        <p className="mt-1">
          В текущем режиме он не выполняет действий в Telegram. Он создаёт 14-дневный план, проверяет готовность аккаунта,
          показывает ближайший шаг, ставит ручную или системную паузу и пишет журнал событий.
        </p>
      </div>

      <WarmupCreateSummary
        canCreate={canCreate}
        isCreating={createMutation.isPending}
        selectedAccountId={selectedAccountId}
        selectedAccountLabel={selectedAccountLabel}
        selectedStrategy={selectedStrategy}
        onCreate={() =>
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
      />
      {createMutation.error ? (
        <Alert className="mt-3" variant="error">
          {createErrorMessage}
        </Alert>
      ) : null}
    </SectionCard>
  )
}
