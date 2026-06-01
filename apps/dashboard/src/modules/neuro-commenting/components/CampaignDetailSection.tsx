// fallow-ignore-file complexity
import { Button, Card, Skeleton } from '@stylisttg/ui'
import { Eye, Pause, Play, Square } from 'lucide-react'
import { useState, type FormEvent } from 'react'

import {
  buildCampaignEditorPayload,
  editorStateFromCampaign,
  type CampaignEditorState,
} from '../formPayloads'
import { useCampaignLifecycleMutation, useNeuroCampaign, useObserveCampaignMutation, useUpdateNeuroCampaign } from '../hooks'
import type { UpdateCampaignPayload } from '../types'

import { CampaignDetailEditor } from './CampaignDetailEditor'
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
    return <Card className="p-4 text-sm text-destructive">Не удалось загрузить данные</Card>
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
          <h2 className="text-base font-semibold text-foreground">{campaign.name}</h2>
          {campaign.description ? <p className="mt-0.5 text-sm text-muted-foreground">{campaign.description}</p> : null}
        </div>
        <CampaignStatusBadge status={campaign.status} />
      </div>

      <div className="grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <span className="text-muted-foreground">Режим</span>
          <p className="font-medium">{campaign.mode}</p>
        </div>
        <div>
          <span className="text-muted-foreground">Отправка</span>
          <p className="font-medium">{campaign.send_mode}</p>
        </div>
        <div>
          <span className="text-muted-foreground">Одобрение</span>
          <p className="font-medium">{campaign.approval_mode}</p>
        </div>
        <div>
          <span className="text-muted-foreground">Dry Run</span>
          <p className="font-medium">{campaign.dry_run ? 'Да' : 'Нет'}</p>
        </div>
      </div>

      <CampaignDetailEditor
        campaign={campaign}
        editorForm={editorForm}
        formError={formError}
        isSaving={updateCampaign.isPending}
        mutationError={mutationError}
        onSubmit={handleEditorSubmit}
        onUpdate={updateEditorForm}
      />

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
          <span className="self-center text-xs text-muted-foreground">
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
