import { Button, Card, EmptyState, FormField, Input, Skeleton } from '@stylisttg/ui'
import { Eye, RefreshCcw, Trash2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'

import { buildTargetPayload, type TargetFormState } from '../formPayloads'
import { useAddCampaignTarget, useNeuroCampaignTargets, useRemoveCampaignTarget, useTargetRuntimeMutations } from '../hooks'
import type { NeuroTargetCreate } from '../types'

export function TargetsSection({ campaignId }: { campaignId: string }) {
  const targetsQuery = useNeuroCampaignTargets(campaignId)
  const addTarget = useAddCampaignTarget(campaignId)
  const removeTarget = useRemoveCampaignTarget(campaignId)
  const runtime = useTargetRuntimeMutations(campaignId)
  const [form, setForm] = useState<TargetFormState>({
    channelRef: '',
    title: '',
    keywords: '',
    excludeKeywords: '',
  })
  const [formError, setFormError] = useState<string | null>(null)
  const targets = targetsQuery.data?.items ?? []

  if (targetsQuery.isError) {
    return <Card className="p-4 text-sm text-red-600">Не удалось загрузить данные</Card>
  }
  if (targetsQuery.isLoading) return <Skeleton className="h-20 w-full" />

  const isMutating = addTarget.isPending || removeTarget.isPending || runtime.observe.isPending || runtime.refreshMetadata.isPending
  const mutationError =
    addTarget.isError || removeTarget.isError || runtime.observe.isError || runtime.refreshMetadata.isError
      ? 'Не удалось сохранить изменения'
      : null

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setFormError(null)
    let payload: NeuroTargetCreate
    try {
      payload = buildTargetPayload(form)
    } catch {
      setFormError('Заполните channel_ref')
      return
    }
    addTarget.mutate(payload, {
      onSuccess: () => setForm({ channelRef: '', title: '', keywords: '', excludeKeywords: '' }),
    })
  }

  return (
    <Card className="p-4">
      <h3 className="mb-3 text-sm font-semibold text-gray-900">Каналы ({targetsQuery.data?.total ?? 0})</h3>
      <form className="mb-3 grid gap-2" onSubmit={handleSubmit}>
        <div className="grid gap-2 sm:grid-cols-2">
          <FormField error={formError} htmlFor="neuro-target-channel">
            <Input
              id="neuro-target-channel"
              placeholder="channel_ref"
              value={form.channelRef}
              onChange={(event) => setForm((current) => ({ ...current, channelRef: event.target.value }))}
            />
          </FormField>
          <Input
            aria-label="title"
            placeholder="title"
            value={form.title}
            onChange={(event) => setForm((current) => ({ ...current, title: event.target.value }))}
          />
          <Input
            aria-label="keywords"
            placeholder="keywords: ai, marketing, tg"
            value={form.keywords}
            onChange={(event) => setForm((current) => ({ ...current, keywords: event.target.value }))}
          />
          <Input
            aria-label="exclude_keywords"
            placeholder="exclude_keywords"
            value={form.excludeKeywords}
            onChange={(event) => setForm((current) => ({ ...current, excludeKeywords: event.target.value }))}
          />
        </div>
        <Button className="w-fit" type="submit" disabled={isMutating || !form.channelRef.trim()}>
          Добавить канал
        </Button>
      </form>
      {mutationError ? <p className="mb-3 text-xs font-medium text-red-500">{mutationError}</p> : null}
      {targets.length === 0 ? (
        <EmptyState title="Нет каналов" description="Добавьте целевые каналы для мониторинга" />
      ) : (
        <div className="space-y-1.5">
          {targets.map((target) => (
            <div key={target.id} className="flex items-center justify-between rounded border border-gray-100 px-3 py-2 text-sm">
              <div>
                <span className="font-medium text-gray-700">{target.channel_ref}</span>
                {target.title ? <span className="ml-2 text-xs text-gray-400">{target.title}</span> : null}
              </div>
              <div className="flex flex-wrap justify-end gap-1.5">
                <Button
                  size="sm"
                  variant="outline"
                  icon={<RefreshCcw className="size-3.5" />}
                  onClick={() => runtime.refreshMetadata.mutate(target.id)}
                  disabled={isMutating}
                >
                  Refresh metadata
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  icon={<Eye className="size-3.5" />}
                  onClick={() => runtime.observe.mutate(target.id)}
                  disabled={isMutating}
                >
                  Observe target
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  icon={<Trash2 className="size-3.5" />}
                  onClick={() => removeTarget.mutate(target.id)}
                  disabled={isMutating}
                >
                  Удалить
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}
