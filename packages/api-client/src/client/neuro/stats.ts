import { unwrap } from '../core'
import type {
  NeuroAccountStats,
  NeuroAttempt,
  NeuroAttemptPage,
  NeuroCampaignStats,
  NeuroChannelRule,
  NeuroChannelRuleCreate,
  NeuroChannelStats,
  NeuroEventPage,
  NeuroFailureReason,
  NeuroPage,
  NeuroPromptPresetList,
  StylistTgClient,
} from '../types'
export async function fetchNeuroAttempts(
  client: StylistTgClient,
  params?: { campaign_id?: string; generated_comment_id?: string; page?: number; limit?: number },
): Promise<NeuroAttemptPage> {
  return unwrap(
    client.openapi.GET('/api/neuro-commenting/attempts', {
      params: { query: params },
    }),
    'neuro attempts',
  )
}

export async function fetchNeuroAttempt(client: StylistTgClient, attemptId: string): Promise<NeuroAttempt> {
  return unwrap(
    client.openapi.GET('/api/neuro-commenting/attempts/{attempt_id}', {
      params: { path: { attempt_id: attemptId } },
    }),
    'neuro attempt',
  )
}

export async function fetchNeuroEvents(
  client: StylistTgClient,
  params?: { campaign_id?: string; page?: number; limit?: number },
): Promise<NeuroEventPage> {
  return unwrap(
    client.openapi.GET('/api/neuro-commenting/events', {
      params: { query: params },
    }),
    'neuro events',
  )
}

export async function fetchNeuroCampaignStats(client: StylistTgClient, campaignId: string): Promise<NeuroCampaignStats> {
  return client.request<NeuroCampaignStats>(`/api/neuro-commenting/campaigns/${encodeURIComponent(campaignId)}/stats`)
}

export async function fetchNeuroAccountStats(
  client: StylistTgClient,
  campaignId: string,
): Promise<NeuroPage<NeuroAccountStats>> {
  return client.request<NeuroPage<NeuroAccountStats>>(
    `/api/neuro-commenting/campaigns/${encodeURIComponent(campaignId)}/account-stats`,
  )
}

export async function fetchNeuroChannelStats(
  client: StylistTgClient,
  campaignId: string,
): Promise<NeuroPage<NeuroChannelStats>> {
  return client.request<NeuroPage<NeuroChannelStats>>(
    `/api/neuro-commenting/campaigns/${encodeURIComponent(campaignId)}/channel-stats`,
  )
}

export async function fetchNeuroCampaignAttempts(
  client: StylistTgClient,
  campaignId: string,
): Promise<NeuroPage<NeuroAttempt>> {
  return client.request<NeuroPage<NeuroAttempt>>(
    `/api/neuro-commenting/campaigns/${encodeURIComponent(campaignId)}/attempts`,
  )
}

export async function fetchNeuroFailureReasons(
  client: StylistTgClient,
  campaignId: string,
): Promise<NeuroPage<NeuroFailureReason>> {
  return client.request<NeuroPage<NeuroFailureReason>>(
    `/api/neuro-commenting/campaigns/${encodeURIComponent(campaignId)}/failure-reasons`,
  )
}

export async function fetchNeuroChannelRules(client: StylistTgClient): Promise<NeuroPage<NeuroChannelRule>> {
  return client.request<NeuroPage<NeuroChannelRule>>('/api/neuro-commenting/channel-rules')
}

export async function fetchNeuroPromptPresets(client: StylistTgClient): Promise<NeuroPromptPresetList> {
  return client.request<NeuroPromptPresetList>('/api/neuro-commenting/prompt-presets')
}

export async function createNeuroChannelRule(
  client: StylistTgClient,
  payload: NeuroChannelRuleCreate,
): Promise<NeuroChannelRule> {
  return client.request<NeuroChannelRule>('/api/neuro-commenting/channel-rules', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function deleteNeuroChannelRule(client: StylistTgClient, ruleId: string): Promise<void> {
  await client.request<void>(`/api/neuro-commenting/channel-rules/${encodeURIComponent(ruleId)}`, { method: 'DELETE' })
}
