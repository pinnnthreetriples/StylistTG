import { unwrap } from '../core'
import type {
  NeuroCampaign,
  NeuroCampaignAccount,
  NeuroCampaignAccountCreate,
  NeuroCampaignAccountPage,
  NeuroCampaignCreate,
  NeuroCampaignPage,
  NeuroCampaignUpdate,
  NeuroLiveReadiness,
  StylistTgClient,
} from '../types'
export async function fetchNeuroCampaigns(
  client: StylistTgClient,
  params?: { page?: number; limit?: number },
): Promise<NeuroCampaignPage> {
  return unwrap(
    client.openapi.GET('/api/neuro-commenting/campaigns', {
      params: { query: params },
    }),
    'neuro campaigns',
  )
}

export async function createNeuroCampaign(
  client: StylistTgClient,
  payload: NeuroCampaignCreate,
): Promise<NeuroCampaign> {
  return unwrap(client.openapi.POST('/api/neuro-commenting/campaigns', { body: payload }), 'create neuro campaign')
}

export async function fetchNeuroCampaign(client: StylistTgClient, campaignId: string): Promise<NeuroCampaign> {
  return unwrap(
    client.openapi.GET('/api/neuro-commenting/campaigns/{campaign_id}', {
      params: { path: { campaign_id: campaignId } },
    }),
    'neuro campaign',
  )
}

export async function updateNeuroCampaign(
  client: StylistTgClient,
  campaignId: string,
  payload: NeuroCampaignUpdate,
): Promise<NeuroCampaign> {
  return unwrap(
    client.openapi.PATCH('/api/neuro-commenting/campaigns/{campaign_id}', {
      params: { path: { campaign_id: campaignId } },
      body: payload,
    }),
    'update neuro campaign',
  )
}

export async function startNeuroCampaign(client: StylistTgClient, campaignId: string): Promise<NeuroCampaign> {
  return unwrap(
    client.openapi.POST('/api/neuro-commenting/campaigns/{campaign_id}/start', {
      params: { path: { campaign_id: campaignId } },
    }),
    'start neuro campaign',
  )
}

export async function pauseNeuroCampaign(client: StylistTgClient, campaignId: string): Promise<NeuroCampaign> {
  return unwrap(
    client.openapi.POST('/api/neuro-commenting/campaigns/{campaign_id}/pause', {
      params: { path: { campaign_id: campaignId } },
    }),
    'pause neuro campaign',
  )
}

export async function stopNeuroCampaign(client: StylistTgClient, campaignId: string): Promise<NeuroCampaign> {
  return unwrap(
    client.openapi.POST('/api/neuro-commenting/campaigns/{campaign_id}/stop', {
      params: { path: { campaign_id: campaignId } },
    }),
    'stop neuro campaign',
  )
}

export async function fetchNeuroLiveReadiness(client: StylistTgClient, campaignId: string): Promise<NeuroLiveReadiness> {
  return client.request<NeuroLiveReadiness>(
    `/api/neuro-commenting/campaigns/${encodeURIComponent(campaignId)}/live-readiness`,
  )
}

export async function fetchNeuroCampaignAccounts(
  client: StylistTgClient,
  campaignId: string,
  params?: { page?: number; limit?: number },
): Promise<NeuroCampaignAccountPage> {
  return unwrap(
    client.openapi.GET('/api/neuro-commenting/campaigns/{campaign_id}/accounts', {
      params: { path: { campaign_id: campaignId }, query: params },
    }),
    'neuro campaign accounts',
  )
}

export async function addNeuroCampaignAccount(
  client: StylistTgClient,
  campaignId: string,
  payload: NeuroCampaignAccountCreate,
): Promise<NeuroCampaignAccount> {
  return unwrap(
    client.openapi.POST('/api/neuro-commenting/campaigns/{campaign_id}/accounts', {
      params: { path: { campaign_id: campaignId } },
      body: payload,
    }),
    'add neuro campaign account',
  )
}

export async function deleteNeuroCampaignAccount(
  client: StylistTgClient,
  campaignId: string,
  accountId: string,
): Promise<void> {
  await client.request<void>(
    `/api/neuro-commenting/campaigns/${encodeURIComponent(campaignId)}/accounts/${encodeURIComponent(accountId)}`,
    { method: 'DELETE' },
  )
}

