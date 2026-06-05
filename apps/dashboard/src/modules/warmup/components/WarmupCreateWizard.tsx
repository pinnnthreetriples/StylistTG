// fallow-ignore-file complexity
// fallow-ignore-reason: Wizard composition shell; step sections are split into dedicated components.
import { Alert, Button, SectionCard } from '@stylisttg/ui'
import { Search } from 'lucide-react'
import { useMemo, useState } from 'react'

import { isApiError } from '@/lib/http'

import { useCreateWarmupSession, useWarmupActionMetadata, useWarmupStrategies, useWarmupValidate } from '../hooks'
import type { WarmupStrategy } from '../types'
import { ActionPresetButtons } from './ActionPresetButtons'
import { ActionMetadataPanel } from './ActionMetadataPanel'
import { WarmupAccountSelector } from './WarmupAccountSelector'
import { WarmupCyclicConfig } from './WarmupCyclicConfig'
import { validateWarmupCycleConfig } from './WarmupCyclicConfigModel'
import {
  WarmupCreateSummary,
  WarmupStrategySelector,
  WarmupValidationPanel,
} from './WarmupCreateWizardSections'

const EMPTY_STRATEGIES: WarmupStrategy[] = []

export function WarmupCreateWizard() {
  const strategiesQuery = useWarmupStrategies()
  const actionMetadataQuery = useWarmupActionMetadata()
  const validateMutation = useWarmupValidate()
  const createMutation = useCreateWarmupSession()
  const [selectedAccountIds, setSelectedAccountIds] = useState<string[]>([])
  const [strategyId, setStrategyId] = useState('')
  const [cyclicEnabled, setCyclicEnabled] = useState(false)
  const [cycleStartHour, setCycleStartHour] = useState(15)
  const [cycleEndHour, setCycleEndHour] = useState(18)
  const [cycleDaysTotal, setCycleDaysTotal] = useState(7)
  const [validatedFor, setValidatedFor] = useState<string | null>(null)

  const strategies = strategiesQuery.data ?? EMPTY_STRATEGIES
  const defaultStrategy =
    strategies.find((strategy) => strategy.preset_kind === 'standard') ??
    strategies.find((strategy) => strategy.name.toLowerCase().includes('стандарт')) ??
    strategies[0]
  const selectedAccountId = selectedAccountIds[0] ?? ''
  const selectedStrategyId = strategyId || defaultStrategy?.id || ''
  const selectedStrategy = strategies.find((strategy) => strategy.id === selectedStrategyId)
  const canValidate = Boolean(selectedAccountId && selectedStrategyId)
  const validation = validateMutation.data
  const selectionKey = `${selectedAccountId}:${selectedStrategyId}`
  const validationMatchesSelection = validatedFor === selectionKey
  const cycleValidation = validateWarmupCycleConfig({
    daysTotal: cycleDaysTotal,
    enabled: cyclicEnabled,
    endHour: cycleEndHour,
    startHour: cycleStartHour,
  })
  const canCreate = Boolean(
    validation?.is_ready && validationMatchesSelection && selectedAccountId && selectedStrategyId && cycleValidation.isValid,
  )
  const createApiError = createMutation.error && isApiError(createMutation.error) ? createMutation.error : null
  const createErrorMessage =
    createApiError
      ? createApiError.error_code === 'WARMUP_QUEUE_UNAVAILABLE'
        ? 'Сессию не удалось поставить в очередь задач. Запустите Redis/RQ worker или отключите live-выполнение подготовки.'
        : createApiError.message
      : 'Не удалось создать сессию. Проверьте готовность аккаунта.'

  const selectedAccountLabel = useMemo(() => selectedAccountId, [selectedAccountId])

  return (
    <SectionCard
      title="Создать сессию подготовки"
      description="Сначала проверяем готовность. После создания аккаунт не выполняет live-действия: модуль только ведёт расписание и аудит."
    >
      <WarmupAccountSelector
        selectedAccountIds={selectedAccountIds}
        onSelectionChange={(nextIds) => {
          setSelectedAccountIds(nextIds)
          setValidatedFor(null)
          createMutation.reset()
        }}
      />
      <div className="mt-3 flex justify-end">
        <Button
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
          Проверить первый выбранный
        </Button>
      </div>
      <WarmupStrategySelector
        selectedStrategyId={selectedStrategyId}
        strategies={strategies}
        onStrategyChange={(nextStrategyId) => {
          setStrategyId(nextStrategyId)
          setValidatedFor(null)
          createMutation.reset()
        }}
      />
      {selectedStrategy ? (
        <ActionPresetButtons
          strategyId={selectedStrategy.id}
          onApplied={() => {
            setValidatedFor(null)
            validateMutation.reset()
          }}
        />
      ) : null}
      <ActionMetadataPanel metadata={actionMetadataQuery.data ?? []} />
      <WarmupCyclicConfig
        apiError={createApiError}
        daysTotal={cycleDaysTotal}
        enabled={cyclicEnabled}
        endHour={cycleEndHour}
        startHour={cycleStartHour}
        onDaysTotalChange={setCycleDaysTotal}
        onEnabledChange={setCyclicEnabled}
        onEndHourChange={setCycleEndHour}
        onStartHourChange={setCycleStartHour}
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
        cycleConfig={
          cyclicEnabled
            ? {
                daysTotal: cycleDaysTotal,
                endHour: cycleEndHour,
                startHour: cycleStartHour,
              }
            : null
        }
        isCreating={createMutation.isPending}
        selectedAccountId={selectedAccountId}
        selectedAccountLabel={selectedAccountLabel}
        selectedStrategy={selectedStrategy}
        onCreate={() =>
          createMutation.mutate(
            {
              accountId: selectedAccountId,
              cycleConfig: cyclicEnabled
                ? {
                    daysTotal: cycleDaysTotal,
                    endHour: cycleEndHour,
                    startHour: cycleStartHour,
                    strategyPreset: selectedStrategy?.preset_kind ?? 'standard',
                  }
                : undefined,
              strategyId: selectedStrategyId,
            },
            {
              onSuccess: () => {
                setSelectedAccountIds([])
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
