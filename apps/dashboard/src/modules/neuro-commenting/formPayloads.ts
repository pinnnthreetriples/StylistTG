import type {
  NeuroCampaign,
  NeuroCampaignAccountCreate,
  NeuroGeneratedComment,
  NeuroGeneratedCommentUpdate,
  NeuroTargetCreate,
  UpdateCampaignPayload,
} from './types'

export type AccountFormState = {
  accountId: string
  rotationWeight: string
  rotationOrder: string
}

export type TargetFormState = {
  channelRef: string
  title: string
  keywords: string
  excludeKeywords: string
}

export type CampaignEditorState = {
  promptTemplate: string
  languageMode: string
  mode: string
  workMode: string
  approvalMode: string
  maxCommentsPerHour: string
  maxCommentsPerDay: string
  delayMinSeconds: string
  delayMaxSeconds: string
  safetyEnabled: boolean
}

export function buildCampaignAccountPayload(form: AccountFormState): NeuroCampaignAccountCreate {
  const accountId = form.accountId.trim()
  const rotationWeight = Number(form.rotationWeight)
  const rotationOrder = Number(form.rotationOrder)
  if (!accountId) throw new Error('account_id required')
  if (!Number.isInteger(rotationWeight) || rotationWeight < 1) throw new Error('rotation_weight invalid')
  if (!Number.isInteger(rotationOrder) || rotationOrder < 0) throw new Error('rotation_order invalid')
  return {
    account_id: accountId,
    rotation_weight: rotationWeight,
    rotation_order: rotationOrder,
  }
}

export function parseKeywordList(value: string): string[] {
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
}

export function buildTargetPayload(form: TargetFormState): NeuroTargetCreate {
  const channelRef = form.channelRef.trim()
  if (!channelRef) throw new Error('channel_ref required')
  const title = form.title.trim()
  return {
    channel_ref: channelRef,
    title: title || null,
    source_type: 'channel',
    keywords: parseKeywordList(form.keywords),
    exclude_keywords: parseKeywordList(form.excludeKeywords),
  }
}

export function visibleGeneratedCommentText(comment: NeuroGeneratedComment): string {
  return comment.final_text ?? comment.edited_text ?? comment.generated_text
}

export function buildGeneratedCommentEditPayload(value: string): NeuroGeneratedCommentUpdate {
  const editedText = value.trim()
  if (!editedText) throw new Error('edited_text required')
  return { edited_text: editedText }
}

export function editorStateFromCampaign(campaign: NeuroCampaign): CampaignEditorState {
  return {
    promptTemplate: campaign.prompt_template ?? '',
    languageMode: campaign.language_mode,
    mode: campaign.mode,
    workMode: campaign.work_mode,
    approvalMode: campaign.approval_mode,
    maxCommentsPerHour: campaign.max_comments_per_hour?.toString() ?? '',
    maxCommentsPerDay: campaign.max_comments_per_day?.toString() ?? '',
    delayMinSeconds: String(campaign.delay_min_seconds),
    delayMaxSeconds: String(campaign.delay_max_seconds),
    safetyEnabled: campaign.safety_enabled,
  }
}

function optionalPositiveInt(value: string, field: string): number | null {
  if (!value.trim()) return null
  const parsed = Number(value)
  if (!Number.isInteger(parsed) || parsed < 1) throw new Error(`${field} invalid`)
  return parsed
}

function requiredNonNegativeInt(value: string, field: string): number {
  const parsed = Number(value)
  if (!Number.isInteger(parsed) || parsed < 0) throw new Error(`${field} invalid`)
  return parsed
}

export function buildCampaignEditorPayload(form: CampaignEditorState): UpdateCampaignPayload {
  const promptTemplate = form.promptTemplate.trim()
  if (promptTemplate.length > 5000) throw new Error('prompt_template too long')
  const delayMinSeconds = requiredNonNegativeInt(form.delayMinSeconds, 'delay_min_seconds')
  const delayMaxSeconds = requiredNonNegativeInt(form.delayMaxSeconds, 'delay_max_seconds')
  if (delayMaxSeconds < delayMinSeconds) throw new Error('delay range invalid')
  return {
    prompt_template: promptTemplate || null,
    language_mode: form.languageMode.trim() || 'auto',
    mode: form.mode as UpdateCampaignPayload['mode'],
    work_mode: form.workMode as UpdateCampaignPayload['work_mode'],
    approval_mode: form.approvalMode as UpdateCampaignPayload['approval_mode'],
    max_comments_per_hour: optionalPositiveInt(form.maxCommentsPerHour, 'max_comments_per_hour'),
    max_comments_per_day: optionalPositiveInt(form.maxCommentsPerDay, 'max_comments_per_day'),
    delay_min_seconds: delayMinSeconds,
    delay_max_seconds: delayMaxSeconds,
    safety_enabled: form.safetyEnabled,
    auto_send_enabled: false,
  }
}
