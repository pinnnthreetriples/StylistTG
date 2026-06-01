import { unwrap } from '../core'
import type {
  NeuroChannelRule,
  NeuroTarget,
  NeuroTargetCreate,
  NeuroTargetPage,
  StylistTgClient,
} from '../types'
export async function fetchNeuroCampaignTargets(
  client: StylistTgClient,
  campaignId: string,
  params?: { page?: number; limit?: number },
): Promise<NeuroTargetPage> {
  return unwrap(
    client.openapi.GET('/api/neuro-commenting/campaigns/{campaign_id}/targets', {
      params: { path: { campaign_id: campaignId }, query: params },
    }),
    'neuro campaign targets',
  )
}

export async function addNeuroCampaignTarget(
  client: StylistTgClient,
  campaignId: string,
  payload: NeuroTargetCreate,
): Promise<NeuroTarget> {
  return unwrap(
    client.openapi.POST('/api/neuro-commenting/campaigns/{campaign_id}/targets', {
      params: { path: { campaign_id: campaignId } },
      body: payload,
    }),
    'add neuro campaign target',
  )
}

export async function deleteNeuroCampaignTarget(
  client: StylistTgClient,
  campaignId: string,
  targetId: string,
): Promise<void> {
  await client.request<void>(
    `/api/neuro-commenting/campaigns/${encodeURIComponent(campaignId)}/targets/${encodeURIComponent(targetId)}`,
    { method: 'DELETE' },
  )
}

export async function blacklistNeuroTarget(client: StylistTgClient, targetId: string): Promise<NeuroChannelRule> {
  return client.request<NeuroChannelRule>(`/api/neuro-commenting/targets/${encodeURIComponent(targetId)}/blacklist`, {
    method: 'POST',
  })
}

export async function whitelistNeuroTarget(client: StylistTgClient, targetId: string): Promise<NeuroChannelRule> {
  return client.request<NeuroChannelRule>(`/api/neuro-commenting/targets/${encodeURIComponent(targetId)}/whitelist`, {
    method: 'POST',
  })
}

export async function pauseNeuroTarget(client: StylistTgClient, targetId: string): Promise<NeuroTarget> {
  return client.request<NeuroTarget>(`/api/neuro-commenting/targets/${encodeURIComponent(targetId)}/pause`, {
    method: 'POST',
  })
}

export async function resumeNeuroTarget(client: StylistTgClient, targetId: string): Promise<NeuroTarget> {
  return client.request<NeuroTarget>(`/api/neuro-commenting/targets/${encodeURIComponent(targetId)}/resume`, {
    method: 'POST',
  })
}
