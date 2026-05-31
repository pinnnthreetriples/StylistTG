import { Button, Card, Input } from '@stylisttg/ui'
import { ArrowLeft, ArrowRight, Check } from 'lucide-react'
import { useState } from 'react'

import { useCreateNeuroCampaign, useNeuroPromptPresets, useUpdateNeuroCampaign } from '../hooks'
import type { ApprovalMode, CampaignMode, WorkMode } from '../types'

type RadioOption<T extends string> = { value: T; label: string; description: string }

function RadioListField<T extends string>({
  legend,
  name,
  options,
  value,
  onChange,
}: {
  legend: string
  name: string
  options: ReadonlyArray<RadioOption<T>>
  value: T
  onChange: (next: T) => void
}) {
  return (
    <fieldset className="grid gap-2">
      <legend className="text-xs font-medium text-foreground">{legend}</legend>
      {options.map((option) => (
        <label
          key={option.value}
          className="flex cursor-pointer items-start gap-3 rounded-md border border-border p-2 text-sm has-[input:checked]:border-border has-[input:checked]:bg-muted"
        >
          <input
            aria-label={option.label}
            type="radio"
            name={name}
            value={option.value}
            checked={value === option.value}
            onChange={() => onChange(option.value)}
          />
          <span>
            <span className="font-medium text-foreground">{option.label}</span>
            <span className="block text-xs text-muted-foreground">{option.description}</span>
          </span>
        </label>
      ))}
    </fieldset>
  )
}

/**
 * Phase 0 Task 4 multi-step campaign creation wizard.
 *
 * Replaces the legacy single-input "Создать" card. Shelfware enum values
 * (`semantic_match`, `scheduled`) are intentionally absent from the option
 * lists because the contract layer rejects them with `feature_not_available`.
 */

type WizardStep = 1 | 2 | 3 | 4

type WizardState = {
  name: string
  description: string
  mode: CampaignMode
  workMode: WorkMode
  approvalMode: ApprovalMode
  promptTemplate: string
}

const initialState: WizardState = {
  name: '',
  description: '',
  mode: 'all_posts',
  workMode: 'manual',
  approvalMode: 'manual_required',
  promptTemplate: '',
}

const supportedModes: { value: CampaignMode; label: string; description: string }[] = [
  { value: 'all_posts', label: 'Все посты', description: 'Комментировать каждый новый пост' },
  { value: 'keyword_match', label: 'По ключевым словам', description: 'Только посты с keywords/exclude_keywords' },
  { value: 'random_posts', label: 'Случайные посты', description: 'Случайная выборка постов' },
]

const supportedWorkModes: { value: WorkMode; label: string; description: string }[] = [
  { value: 'manual', label: 'Ручной запуск', description: 'Только через кнопку «observe»' },
  { value: 'by_comment_count', label: 'По счётчику комментариев', description: 'Авто-останов после N комментариев' },
  { value: 'by_time_window', label: 'По окну времени', description: 'Работа в указанный временной интервал' },
]

const supportedApprovalModes: { value: ApprovalMode; label: string; description: string }[] = [
  { value: 'manual_required', label: 'Ручное подтверждение', description: 'Все комментарии требуют approve' },
  { value: 'trusted_auto', label: 'Trusted auto', description: 'Авто-approve если safety=passed' },
  { value: 'auto', label: 'Auto', description: 'Авто-approve без safety-проверки' },
]

export function CampaignWizard({
  onCreated,
  onCancel,
}: {
  onCreated: (campaignId: string) => void
  onCancel: () => void
}) {
  const [step, setStep] = useState<WizardStep>(1)
  const [state, setState] = useState<WizardState>(initialState)
  const [error, setError] = useState<string | null>(null)
  const [selectedPresetId, setSelectedPresetId] = useState<string>('')
  const createMutation = useCreateNeuroCampaign()
  const updateMutation = useUpdateNeuroCampaign('')
  const presetsQuery = useNeuroPromptPresets()

  const canAdvance =
    (step === 1 && state.name.trim().length > 0) ||
    step === 2 ||
    step === 3 ||
    step === 4

  const stepLabels = ['Название', 'Режим', 'Промпт', 'Подтверждение']

  const submit = async () => {
    if (!state.name.trim()) {
      setError('Название обязательно')
      return
    }
    try {
      const created = await createMutation.mutateAsync({
        name: state.name.trim(),
        description: state.description.trim() || undefined,
      })
      // Apply non-default settings via update so we don't depend on
      // server-side defaults differing from the wizard intent.
      if (
        state.mode !== 'all_posts' ||
        state.workMode !== 'manual' ||
        state.approvalMode !== 'manual_required' ||
        state.promptTemplate.trim().length > 0
      ) {
        try {
          await fetch(`/api/neuro-commenting/campaigns/${created.id}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({
              mode: state.mode,
              work_mode: state.workMode,
              approval_mode: state.approvalMode,
              prompt_template: state.promptTemplate.trim() || null,
            }),
          })
        } catch {
          // Update failures are non-fatal in the wizard - the campaign exists
          // and the user can finish configuration in the detail view.
        }
      }
      onCreated(created.id)
    } catch {
      setError('Не удалось создать кампанию')
    }
  }

  return (
    <Card className="p-4">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-foreground">Новая кампания</h3>
        <ol className="flex gap-2 text-xs text-muted-foreground">
          {stepLabels.map((label, idx) => {
            const stepNumber = idx + 1
            const isActive = stepNumber === step
            const isDone = stepNumber < step
            return (
              <li
                key={label}
                className={
                  isActive
                    ? 'rounded-md bg-muted px-2 py-0.5 font-medium text-foreground'
                    : isDone
                      ? 'text-primary'
                      : 'text-muted-foreground'
                }
              >
                {stepNumber}. {label}
              </li>
            )
          })}
        </ol>
      </div>

      {step === 1 ? (
        <div className="grid gap-3">
          <label className="grid gap-1 text-xs font-medium text-foreground" htmlFor="campaign-name">
            Название
            <Input
              id="campaign-name"
              aria-label="Название кампании"
              value={state.name}
              onChange={(e) => setState((s) => ({ ...s, name: e.target.value }))}
              placeholder="Запуск B2B"
            />
          </label>
          <label className="grid gap-1 text-xs font-medium text-foreground">
            Описание
            <textarea
              aria-label="Описание кампании"
              className="min-h-20 rounded-md border border-border bg-card px-3 py-2 text-sm focus:border-border focus:outline-none focus:ring-2 focus:ring-ring"
              value={state.description}
              onChange={(e) => setState((s) => ({ ...s, description: e.target.value }))}
              placeholder="Опционально"
            />
          </label>
        </div>
      ) : null}

      {step === 2 ? (
        <div className="grid gap-4">
          <RadioListField
            legend="Режим подбора постов"
            name="mode"
            options={supportedModes}
            value={state.mode}
            onChange={(value) => setState((s) => ({ ...s, mode: value }))}
          />
          <RadioListField
            legend="Режим работы"
            name="workMode"
            options={supportedWorkModes}
            value={state.workMode}
            onChange={(value) => setState((s) => ({ ...s, workMode: value }))}
          />
        </div>
      ) : null}

      {step === 3 ? (
        <div className="grid gap-4">
          <label className="grid gap-1 text-xs font-medium text-foreground">
            Пресет промпта
            <select
              aria-label="Пресет промпта"
              className="rounded-md border border-border bg-card px-3 py-2 text-sm focus:border-border focus:outline-none focus:ring-2 focus:ring-ring"
              value={selectedPresetId}
              onChange={(event) => {
                const id = event.target.value
                setSelectedPresetId(id)
                const preset = presetsQuery.data?.items.find((item) => item.id === id)
                if (preset) {
                  setState((s) => ({ ...s, promptTemplate: preset.prompt_template }))
                }
              }}
            >
              <option value="">— без пресета —</option>
              {(presetsQuery.data?.items ?? []).map((preset) => (
                <option key={preset.id} value={preset.id}>
                  {preset.name} ({preset.language})
                </option>
              ))}
            </select>
          </label>
          <label className="grid gap-1 text-xs font-medium text-foreground">
            Промпт для AI
            <textarea
              aria-label="Промпт для AI"
              className="min-h-28 rounded-md border border-border bg-card px-3 py-2 text-sm focus:border-border focus:outline-none focus:ring-2 focus:ring-ring"
              value={state.promptTemplate}
              onChange={(e) => setState((s) => ({ ...s, promptTemplate: e.target.value }))}
              placeholder="Например: «Напиши короткий нативный комментарий по теме поста, 3-7 слов»"
            />
          </label>
          <RadioListField
            legend="Режим одобрения"
            name="approvalMode"
            options={supportedApprovalModes}
            value={state.approvalMode}
            onChange={(value) => setState((s) => ({ ...s, approvalMode: value }))}
          />
        </div>
      ) : null}

      {step === 4 ? (
        <dl className="grid gap-2 text-xs text-foreground">
          <div className="flex justify-between">
            <dt className="font-medium">Название:</dt>
            <dd>{state.name || <span className="text-muted-foreground">—</span>}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="font-medium">Описание:</dt>
            <dd className="max-w-[60%] text-right">{state.description || <span className="text-muted-foreground">—</span>}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="font-medium">Режим:</dt>
            <dd>{supportedModes.find((m) => m.value === state.mode)?.label}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="font-medium">Работа:</dt>
            <dd>{supportedWorkModes.find((m) => m.value === state.workMode)?.label}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="font-medium">Одобрение:</dt>
            <dd>{supportedApprovalModes.find((m) => m.value === state.approvalMode)?.label}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="font-medium">Промпт:</dt>
            <dd className="max-w-[60%] truncate text-right">
              {state.promptTemplate || <span className="text-muted-foreground">по умолчанию</span>}
            </dd>
          </div>
        </dl>
      ) : null}

      {error ? <p className="mt-3 text-xs font-medium text-destructive">{error}</p> : null}

      <div className="mt-4 flex justify-between gap-2">
        <Button
          size="sm"
          variant="outline"
          icon={<ArrowLeft className="size-3" />}
          onClick={() => {
            if (step === 1) {
              onCancel()
            } else {
              setStep((s) => (s - 1) as WizardStep)
            }
          }}
          disabled={createMutation.isPending || updateMutation.isPending}
        >
          {step === 1 ? 'Отмена' : 'Назад'}
        </Button>
        {step < 4 ? (
          <Button
            size="sm"
            icon={<ArrowRight className="size-3" />}
            onClick={() => {
              if (step === 1 && !state.name.trim()) {
                setError('Название обязательно')
                return
              }
              setError(null)
              setStep((s) => (s + 1) as WizardStep)
            }}
            disabled={!canAdvance}
          >
            Далее
          </Button>
        ) : (
          <Button
            size="sm"
            variant="primary"
            icon={<Check className="size-3" />}
            onClick={() => void submit()}
            disabled={createMutation.isPending || !state.name.trim()}
          >
            Создать
          </Button>
        )}
      </div>
    </Card>
  )
}
