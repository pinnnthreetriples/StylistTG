import { Button, Card, EmptyState, FormField, Input, Skeleton } from '@stylisttg/ui'
import { Ban, CheckCircle2, Eye, Pause, Play, RefreshCcw, Trash2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'

import { buildTargetPayload, type TargetFormState } from '../formPayloads'
import {
  useAddCampaignTarget,
  useNeuroCampaignTargets,
  useRemoveCampaignTarget,
  useTargetRuleActions,
  useTargetRuntimeMutations,
} from '../hooks'
import type { NeuroTargetCreate } from '../types'

export type NeuroTargetActionRow = {
  id: string
  channel_ref: string
  status: string
}

type TargetsSectionProps =
  | { campaignId: string }
  | {
      targets: NeuroTargetActionRow[]
      onPause?: (targetId: string) => void
      onResume?: (targetId: string) => void
      onBlacklist?: (targetId: string) => void
      onWhitelist?: (targetId: string) => void
    }

export function TargetsSection(props: TargetsSectionProps) {
  if ('targets' in props) {
    return (
      <TargetActionTable
        targets={props.targets}
        onPause={props.onPause}
        onResume={props.onResume}
        onBlacklist={props.onBlacklist}
        onWhitelist={props.onWhitelist}
      />
    )
  }

  return <CampaignTargetsSection campaignId={props.campaignId} />
}

function CampaignTargetsSection({ campaignId }: { campaignId: string }) {
  const targetsQuery = useNeuroCampaignTargets(campaignId)
  const addTarget = useAddCampaignTarget(campaignId)
  const removeTarget = useRemoveCampaignTarget(campaignId)
  const runtime = useTargetRuntimeMutations(campaignId)
  const ruleActions = useTargetRuleActions(campaignId)
  const [form, setForm] = useState<TargetFormState>({
    channelRef: '',
    title: '',
    keywords: '',
    excludeKeywords: '',
  })
  const [formError, setFormError] = useState<string | null>(null)
  const targets = targetsQuery.data?.items ?? []

  if (targetsQuery.isError) {
    return <Card className="p-4 text-sm text-destructive">Не удалось загрузить данные</Card>
  }
  if (targetsQuery.isLoading) return <Skeleton className="h-20 w-full" />

  const isMutating =
    addTarget.isPending ||
    removeTarget.isPending ||
    runtime.observe.isPending ||
    runtime.refreshMetadata.isPending ||
    ruleActions.pause.isPending ||
    ruleActions.resume.isPending ||
    ruleActions.blacklist.isPending ||
    ruleActions.whitelist.isPending
  const mutationError =
    addTarget.isError ||
    removeTarget.isError ||
    runtime.observe.isError ||
    runtime.refreshMetadata.isError ||
    ruleActions.pause.isError ||
    ruleActions.resume.isError ||
    ruleActions.blacklist.isError ||
    ruleActions.whitelist.isError
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
      <h3 className="mb-3 text-sm font-semibold text-foreground">Каналы ({targetsQuery.data?.total ?? 0})</h3>
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
      {mutationError ? <p className="mb-3 text-xs font-medium text-destructive">{mutationError}</p> : null}
      {targets.length === 0 ? (
        <EmptyState title="Нет каналов" description="Добавьте целевые каналы для мониторинга" />
      ) : (
        <div className="space-y-1.5">
          {targets.map((target) => (
            <div key={target.id} className="flex items-center justify-between rounded border border-border px-3 py-2 text-sm">
              <div>
                <span className="font-medium text-foreground">{target.channel_ref}</span>
                {target.title ? <span className="ml-2 text-xs text-muted-foreground">{target.title}</span> : null}
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
                  icon={<Pause className="size-3.5" />}
                  onClick={() => ruleActions.pause.mutate(target.id)}
                  disabled={isMutating}
                >
                  Pause
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  icon={<Play className="size-3.5" />}
                  onClick={() => ruleActions.resume.mutate(target.id)}
                  disabled={isMutating}
                >
                  Resume
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  icon={<Ban className="size-3.5" />}
                  onClick={() => ruleActions.blacklist.mutate(target.id)}
                  disabled={isMutating}
                >
                  Blacklist
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  icon={<CheckCircle2 className="size-3.5" />}
                  onClick={() => ruleActions.whitelist.mutate(target.id)}
                  disabled={isMutating}
                >
                  Whitelist
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

function TargetActionTable({
  targets,
  onPause,
  onResume,
  onBlacklist,
  onWhitelist,
}: {
  targets: NeuroTargetActionRow[]
  onPause?: (targetId: string) => void
  onResume?: (targetId: string) => void
  onBlacklist?: (targetId: string) => void
  onWhitelist?: (targetId: string) => void
}) {
  if (targets.length === 0) return <section aria-label="Neuro targets">No targets yet</section>

  return (
    <section aria-label="Neuro targets">
      <table>
        <tbody>
          {targets.map((target) => (
            <tr key={target.id}>
              <td>{target.channel_ref}</td>
              <td>{target.status}</td>
              <td>
                <button type="button" onClick={() => onPause?.(target.id)}>
                  Pause
                </button>
                <button type="button" onClick={() => onResume?.(target.id)}>
                  Resume
                </button>
                <button type="button" onClick={() => onBlacklist?.(target.id)}>
                  Blacklist
                </button>
                <button type="button" onClick={() => onWhitelist?.(target.id)}>
                  Whitelist
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}
