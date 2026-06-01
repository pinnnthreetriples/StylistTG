import { Button, FormField, Input, Select } from '@stylisttg/ui'
import { Save } from 'lucide-react'
import type { FormEvent } from 'react'

import type { CampaignEditorState } from '../formPayloads'
import type { NeuroCampaign } from '../types'

export function CampaignDetailEditor({
  campaign,
  editorForm,
  formError,
  isSaving,
  mutationError,
  onSubmit,
  onUpdate,
}: {
  campaign: NeuroCampaign
  editorForm: CampaignEditorState
  formError: string | null
  isSaving: boolean
  mutationError: string | null
  onSubmit: (event: FormEvent<HTMLFormElement>) => void
  onUpdate: (patch: Partial<CampaignEditorState>) => void
}) {
  return (
    <form className="space-y-3 border-t border-border pt-4" onSubmit={onSubmit}>
      <FormField label="Prompt" error={formError} htmlFor="neuro-campaign-prompt">
        <textarea
          id="neuro-campaign-prompt"
          aria-label="Prompt"
          className="min-h-24 rounded-md border border-border bg-card px-3 py-2 text-sm focus:border-border focus:outline-none focus:ring-2 focus:ring-ring"
          maxLength={5000}
          value={editorForm.promptTemplate}
          onChange={(event) => onUpdate({ promptTemplate: event.target.value })}
        />
      </FormField>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <FormField label="Язык" htmlFor="neuro-campaign-language">
          <Input id="neuro-campaign-language" value={editorForm.languageMode} onChange={(event) => onUpdate({ languageMode: event.target.value })} />
        </FormField>
        <FormField label="Режим" htmlFor="neuro-campaign-mode">
          <Select id="neuro-campaign-mode" value={editorForm.mode} onChange={(event) => onUpdate({ mode: event.target.value })}>
            <option value="all_posts">all_posts</option>
            <option value="keyword_match">keyword_match</option>
            <option value="random_posts">random_posts</option>
            <option value="semantic_match">semantic_match</option>
          </Select>
        </FormField>
        <FormField label="Work mode" htmlFor="neuro-campaign-work-mode">
          <Select id="neuro-campaign-work-mode" value={editorForm.workMode} onChange={(event) => onUpdate({ workMode: event.target.value })}>
            <option value="manual">manual</option>
            <option value="by_comment_count">by_comment_count</option>
            <option value="by_time_window">by_time_window</option>
            <option value="scheduled">scheduled</option>
          </Select>
        </FormField>
        <FormField label="Approval" htmlFor="neuro-campaign-approval">
          <Select id="neuro-campaign-approval" value={editorForm.approvalMode} onChange={(event) => onUpdate({ approvalMode: event.target.value })}>
            <option value="manual_required">manual_required</option>
            <option value="trusted_auto">trusted_auto</option>
            <option value="auto">auto</option>
          </Select>
        </FormField>
        <FormField label="В час" htmlFor="neuro-campaign-hour-limit">
          <Input id="neuro-campaign-hour-limit" min={1} type="number" value={editorForm.maxCommentsPerHour} onChange={(event) => onUpdate({ maxCommentsPerHour: event.target.value })} />
        </FormField>
        <FormField label="В день" htmlFor="neuro-campaign-day-limit">
          <Input id="neuro-campaign-day-limit" min={1} type="number" value={editorForm.maxCommentsPerDay} onChange={(event) => onUpdate({ maxCommentsPerDay: event.target.value })} />
        </FormField>
        <FormField label="Delay min" htmlFor="neuro-campaign-delay-min">
          <Input id="neuro-campaign-delay-min" min={0} type="number" value={editorForm.delayMinSeconds} onChange={(event) => onUpdate({ delayMinSeconds: event.target.value })} />
        </FormField>
        <FormField label="Delay max" htmlFor="neuro-campaign-delay-max">
          <Input id="neuro-campaign-delay-max" min={60} type="number" value={editorForm.delayMaxSeconds} onChange={(event) => onUpdate({ delayMaxSeconds: event.target.value })} />
        </FormField>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <label className="inline-flex items-center gap-2 text-sm text-foreground">
          <input
            aria-label="Safety enabled"
            checked={editorForm.safetyEnabled}
            className="size-4"
            type="checkbox"
            onChange={(event) => onUpdate({ safetyEnabled: event.target.checked })}
          />
          Safety enabled
        </label>
        <span className="rounded border border-border bg-muted px-2 py-1 text-xs text-muted-foreground">auto_send_enabled: false</span>
        <span className="rounded border border-border bg-muted px-2 py-1 text-xs text-muted-foreground">send_mode: {campaign.send_mode}</span>
        <span className="rounded border border-border bg-muted px-2 py-1 text-xs text-muted-foreground">comment_as_channel: coming soon</span>
        <span className="rounded border border-border bg-muted px-2 py-1 text-xs text-muted-foreground">emoji_then_edit: coming soon</span>
        <Button size="sm" type="submit" icon={<Save className="size-3.5" />} disabled={isSaving}>
          Сохранить настройки
        </Button>
      </div>
      {mutationError ? <p className="text-xs font-medium text-destructive">{mutationError}</p> : null}
    </form>
  )
}
