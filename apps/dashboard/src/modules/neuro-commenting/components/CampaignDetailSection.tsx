import { Button, Card, FormField, Input, Select, Skeleton } from '@stylisttg/ui'
import { Eye, Pause, Play, Save, Square } from 'lucide-react'
import { useState, type FormEvent } from 'react'

import {
  buildCampaignEditorPayload,
  editorStateFromCampaign,
  type CampaignEditorState,
} from '../formPayloads'
import { useCampaignLifecycleMutation, useNeuroCampaign, useObserveCampaignMutation, useUpdateNeuroCampaign } from '../hooks'
import type { UpdateCampaignPayload } from '../types'

import { CampaignStatusBadge } from './CampaignStatusBadge'

export function CampaignDetailSection({ campaignId }: { campaignId: string }) {
  const campaignQuery = useNeuroCampaign(campaignId)
  const lifecycle = useCampaignLifecycleMutation(campaignId)
  const observe = useObserveCampaignMutation(campaignId)
  const updateCampaign = useUpdateNeuroCampaign(campaignId)
  const [form, setForm] = useState<{ campaignId: string; value: CampaignEditorState } | null>(null)
  const [formError, setFormError] = useState<string | null>(null)
  const campaign = campaignQuery.data

  if (campaignQuery.isError) {
    return <Card className="p-4 text-sm text-red-600">Не удалось загрузить данные</Card>
  }
  if (campaignQuery.isLoading) {
    return <Skeleton className="h-32 w-full" />
  }
  if (!campaign) {
    return <Skeleton className="h-32 w-full" />
  }

  const isDraft = campaign.status === 'draft'
  const isRunning = campaign.status === 'running'
  const isPaused = campaign.status === 'paused'
  const editorForm = form?.campaignId === campaign.id ? form.value : editorStateFromCampaign(campaign)
  const mutationError = updateCampaign.isError || lifecycle.isError || observe.isError ? 'Не удалось сохранить изменения' : null
  const updateEditorForm = (patch: Partial<CampaignEditorState>) => {
    setForm({ campaignId: campaign.id, value: { ...editorForm, ...patch } })
  }

  const handleEditorSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setFormError(null)
    let payload: UpdateCampaignPayload
    try {
      payload = buildCampaignEditorPayload(editorForm)
    } catch {
      setFormError('Проверьте prompt, лимиты и диапазон задержки')
      return
    }
    updateCampaign.mutate(payload, { onSuccess: () => setForm(null) })
  }

  return (
    <Card className="space-y-4 p-4">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-base font-semibold text-gray-900">{campaign.name}</h2>
          {campaign.description ? <p className="mt-0.5 text-sm text-gray-500">{campaign.description}</p> : null}
        </div>
        <CampaignStatusBadge status={campaign.status} />
      </div>

      <div className="grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <span className="text-gray-500">Режим</span>
          <p className="font-medium">{campaign.mode}</p>
        </div>
        <div>
          <span className="text-gray-500">Отправка</span>
          <p className="font-medium">{campaign.send_mode}</p>
        </div>
        <div>
          <span className="text-gray-500">Одобрение</span>
          <p className="font-medium">{campaign.approval_mode}</p>
        </div>
        <div>
          <span className="text-gray-500">Dry Run</span>
          <p className="font-medium">{campaign.dry_run ? 'Да' : 'Нет'}</p>
        </div>
      </div>

      <form className="space-y-3 border-t border-gray-100 pt-4" onSubmit={handleEditorSubmit}>
        <FormField label="Prompt" error={formError} htmlFor="neuro-campaign-prompt">
          <textarea
            id="neuro-campaign-prompt"
            className="min-h-24 rounded-md border border-gray-200 bg-white px-3 py-2 text-sm focus:border-navy-400 focus:outline-none focus:ring-2 focus:ring-navy-100"
            maxLength={5000}
            value={editorForm.promptTemplate}
            onChange={(event) => updateEditorForm({ promptTemplate: event.target.value })}
          />
        </FormField>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <FormField label="Язык" htmlFor="neuro-campaign-language">
            <Input
              id="neuro-campaign-language"
              value={editorForm.languageMode}
              onChange={(event) => updateEditorForm({ languageMode: event.target.value })}
            />
          </FormField>
          <FormField label="Режим" htmlFor="neuro-campaign-mode">
            <Select
              id="neuro-campaign-mode"
              value={editorForm.mode}
              onChange={(event) => updateEditorForm({ mode: event.target.value })}
            >
              <option value="all_posts">all_posts</option>
              <option value="keyword_match">keyword_match</option>
              <option value="random_posts">random_posts</option>
              <option value="semantic_match">semantic_match</option>
            </Select>
          </FormField>
          <FormField label="Work mode" htmlFor="neuro-campaign-work-mode">
            <Select
              id="neuro-campaign-work-mode"
              value={editorForm.workMode}
              onChange={(event) => updateEditorForm({ workMode: event.target.value })}
            >
              <option value="manual">manual</option>
              <option value="by_comment_count">by_comment_count</option>
              <option value="by_time_window">by_time_window</option>
              <option value="scheduled">scheduled</option>
            </Select>
          </FormField>
          <FormField label="Approval" htmlFor="neuro-campaign-approval">
            <Select
              id="neuro-campaign-approval"
              value={editorForm.approvalMode}
              onChange={(event) => updateEditorForm({ approvalMode: event.target.value })}
            >
              <option value="manual_required">manual_required</option>
              <option value="trusted_auto">trusted_auto</option>
              <option value="auto">auto</option>
            </Select>
          </FormField>
          <FormField label="В час" htmlFor="neuro-campaign-hour-limit">
            <Input
              id="neuro-campaign-hour-limit"
              min={1}
              type="number"
              value={editorForm.maxCommentsPerHour}
              onChange={(event) => updateEditorForm({ maxCommentsPerHour: event.target.value })}
            />
          </FormField>
          <FormField label="В день" htmlFor="neuro-campaign-day-limit">
            <Input
              id="neuro-campaign-day-limit"
              min={1}
              type="number"
              value={editorForm.maxCommentsPerDay}
              onChange={(event) => updateEditorForm({ maxCommentsPerDay: event.target.value })}
            />
          </FormField>
          <FormField label="Delay min" htmlFor="neuro-campaign-delay-min">
            <Input
              id="neuro-campaign-delay-min"
              min={0}
              type="number"
              value={editorForm.delayMinSeconds}
              onChange={(event) => updateEditorForm({ delayMinSeconds: event.target.value })}
            />
          </FormField>
          <FormField label="Delay max" htmlFor="neuro-campaign-delay-max">
            <Input
              id="neuro-campaign-delay-max"
              min={60}
              type="number"
              value={editorForm.delayMaxSeconds}
              onChange={(event) => updateEditorForm({ delayMaxSeconds: event.target.value })}
            />
          </FormField>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <label className="inline-flex items-center gap-2 text-sm text-gray-700">
            <input
              checked={editorForm.safetyEnabled}
              className="size-4"
              type="checkbox"
              onChange={(event) => updateEditorForm({ safetyEnabled: event.target.checked })}
            />
            Safety enabled
          </label>
          <span className="rounded border border-gray-200 bg-gray-50 px-2 py-1 text-xs text-gray-500">
            auto_send_enabled: false
          </span>
          <span className="rounded border border-gray-200 bg-gray-50 px-2 py-1 text-xs text-gray-500">
            send_mode: {campaign.send_mode}
          </span>
          <span className="rounded border border-gray-200 bg-gray-50 px-2 py-1 text-xs text-gray-500">
            comment_as_channel: coming soon
          </span>
          <span className="rounded border border-gray-200 bg-gray-50 px-2 py-1 text-xs text-gray-500">
            emoji_then_edit: coming soon
          </span>
          <Button
            size="sm"
            type="submit"
            icon={<Save className="size-3.5" />}
            disabled={updateCampaign.isPending}
          >
            Сохранить настройки
          </Button>
        </div>
        {mutationError ? <p className="text-xs font-medium text-red-500">{mutationError}</p> : null}
      </form>

      <div className="flex gap-2">
        <Button
          size="sm"
          variant="outline"
          icon={<Eye className="size-3.5" />}
          onClick={() => observe.mutate()}
          disabled={observe.isPending}
        >
          Observe campaign now
        </Button>
        {observe.data ? (
          <span className="self-center text-xs text-gray-500">
            Accepted: {observe.data.job_id}
          </span>
        ) : null}
        {isDraft || isPaused ? (
          <Button
            size="sm"
            variant="primary"
            icon={<Play className="size-3.5" />}
            onClick={() => lifecycle.mutate('start')}
            disabled={lifecycle.isPending}
          >
            Запустить
          </Button>
        ) : null}
        {isRunning ? (
          <Button
            size="sm"
            variant="secondary"
            icon={<Pause className="size-3.5" />}
            onClick={() => lifecycle.mutate('pause')}
            disabled={lifecycle.isPending}
          >
            Пауза
          </Button>
        ) : null}
        {isRunning || isPaused ? (
          <Button
            size="sm"
            variant="danger"
            icon={<Square className="size-3.5" />}
            onClick={() => lifecycle.mutate('stop')}
            disabled={lifecycle.isPending}
          >
            Остановить
          </Button>
        ) : null}
      </div>
    </Card>
  )
}
