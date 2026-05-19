import { Button, Card, Input } from '@stylisttg/ui'
import { ArrowLeft, ArrowRight, Check } from 'lucide-react'
import { useState } from 'react'

import { useCreateNeuroCampaign, useUpdateNeuroCampaign } from '../hooks'
import type { ApprovalMode, CampaignMode, WorkMode } from '../types'

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
  const createMutation = useCreateNeuroCampaign()
  const updateMutation = useUpdateNeuroCampaign('')

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
        <h3 className="text-sm font-semibold text-gray-900">Новая кампания</h3>
        <ol className="flex gap-2 text-xs text-gray-500">
          {stepLabels.map((label, idx) => {
            const stepNumber = idx + 1
            const isActive = stepNumber === step
            const isDone = stepNumber < step
            return (
              <li
                key={label}
                className={
                  isActive
                    ? 'rounded-md bg-navy-50 px-2 py-0.5 font-medium text-navy-900'
                    : isDone
                      ? 'text-emerald-600'
                      : 'text-gray-400'
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
          <label className="grid gap-1 text-xs font-medium text-gray-700">
            Название
            <Input
              value={state.name}
              onChange={(e) => setState((s) => ({ ...s, name: e.target.value }))}
              placeholder="Запуск B2B"
            />
          </label>
          <label className="grid gap-1 text-xs font-medium text-gray-700">
            Описание
            <textarea
              className="min-h-20 rounded-md border border-gray-200 bg-white px-3 py-2 text-sm focus:border-navy-400 focus:outline-none focus:ring-2 focus:ring-navy-100"
              value={state.description}
              onChange={(e) => setState((s) => ({ ...s, description: e.target.value }))}
              placeholder="Опционально"
            />
          </label>
        </div>
      ) : null}

      {step === 2 ? (
        <div className="grid gap-4">
          <fieldset className="grid gap-2">
            <legend className="text-xs font-medium text-gray-700">Режим подбора постов</legend>
            {supportedModes.map((option) => (
              <label
                key={option.value}
                className="flex cursor-pointer items-start gap-3 rounded-md border border-gray-200 p-2 text-sm has-[input:checked]:border-navy-300 has-[input:checked]:bg-navy-50"
              >
                <input
                  type="radio"
                  name="mode"
                  value={option.value}
                  checked={state.mode === option.value}
                  onChange={() => setState((s) => ({ ...s, mode: option.value }))}
                />
                <span>
                  <span className="font-medium text-gray-900">{option.label}</span>
                  <span className="block text-xs text-gray-500">{option.description}</span>
                </span>
              </label>
            ))}
          </fieldset>
          <fieldset className="grid gap-2">
            <legend className="text-xs font-medium text-gray-700">Режим работы</legend>
            {supportedWorkModes.map((option) => (
              <label
                key={option.value}
                className="flex cursor-pointer items-start gap-3 rounded-md border border-gray-200 p-2 text-sm has-[input:checked]:border-navy-300 has-[input:checked]:bg-navy-50"
              >
                <input
                  type="radio"
                  name="workMode"
                  value={option.value}
                  checked={state.workMode === option.value}
                  onChange={() => setState((s) => ({ ...s, workMode: option.value }))}
                />
                <span>
                  <span className="font-medium text-gray-900">{option.label}</span>
                  <span className="block text-xs text-gray-500">{option.description}</span>
                </span>
              </label>
            ))}
          </fieldset>
        </div>
      ) : null}

      {step === 3 ? (
        <div className="grid gap-4">
          <label className="grid gap-1 text-xs font-medium text-gray-700">
            Промпт для AI
            <textarea
              className="min-h-28 rounded-md border border-gray-200 bg-white px-3 py-2 text-sm focus:border-navy-400 focus:outline-none focus:ring-2 focus:ring-navy-100"
              value={state.promptTemplate}
              onChange={(e) => setState((s) => ({ ...s, promptTemplate: e.target.value }))}
              placeholder="Например: «Напиши короткий нативный комментарий по теме поста, 3-7 слов»"
            />
          </label>
          <fieldset className="grid gap-2">
            <legend className="text-xs font-medium text-gray-700">Режим одобрения</legend>
            {supportedApprovalModes.map((option) => (
              <label
                key={option.value}
                className="flex cursor-pointer items-start gap-3 rounded-md border border-gray-200 p-2 text-sm has-[input:checked]:border-navy-300 has-[input:checked]:bg-navy-50"
              >
                <input
                  type="radio"
                  name="approvalMode"
                  value={option.value}
                  checked={state.approvalMode === option.value}
                  onChange={() => setState((s) => ({ ...s, approvalMode: option.value }))}
                />
                <span>
                  <span className="font-medium text-gray-900">{option.label}</span>
                  <span className="block text-xs text-gray-500">{option.description}</span>
                </span>
              </label>
            ))}
          </fieldset>
        </div>
      ) : null}

      {step === 4 ? (
        <dl className="grid gap-2 text-xs text-gray-700">
          <div className="flex justify-between">
            <dt className="font-medium">Название:</dt>
            <dd>{state.name || <span className="text-gray-400">—</span>}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="font-medium">Описание:</dt>
            <dd className="max-w-[60%] text-right">{state.description || <span className="text-gray-400">—</span>}</dd>
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
              {state.promptTemplate || <span className="text-gray-400">по умолчанию</span>}
            </dd>
          </div>
        </dl>
      ) : null}

      {error ? <p className="mt-3 text-xs font-medium text-red-500">{error}</p> : null}

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
