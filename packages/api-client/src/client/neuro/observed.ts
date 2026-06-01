import { unwrap } from '../core'
import type {
  NeuroAcceptedJob,
  NeuroGenerateObservedPostRequest,
  NeuroObservedPost,
  NeuroObservedPostPage,
  NeuroObserveCampaignRequest,
  NeuroObserveTargetRequest,
  StylistTgClient,
} from '../types'
export async function fetchNeuroObservedPosts(
  client: StylistTgClient,
  params?: { campaign_id?: string; target_id?: string; page?: number; limit?: number },
): Promise<NeuroObservedPostPage> {
  return unwrap(
    client.openapi.GET('/api/neuro-commenting/observed-posts', {
      params: { query: params },
    }),
    'neuro observed posts',
  )
}

export async function fetchNeuroObservedPost(
  client: StylistTgClient,
  observedPostId: string,
): Promise<NeuroObservedPost> {
  return unwrap(
    client.openapi.GET('/api/neuro-commenting/observed-posts/{observed_post_id}', {
      params: { path: { observed_post_id: observedPostId } },
    }),
    'neuro observed post',
  )
}

export async function observeNeuroCampaign(
  client: StylistTgClient,
  campaignId: string,
  payload: NeuroObserveCampaignRequest = { generate: true },
): Promise<NeuroAcceptedJob> {
  return unwrap(
    client.openapi.POST('/api/neuro-commenting/campaigns/{campaign_id}/observe', {
      params: { path: { campaign_id: campaignId } },
      body: payload,
    }),
    'observe neuro campaign',
  )
}

export async function observeNeuroTarget(
  client: StylistTgClient,
  campaignId: string,
  targetId: string,
  payload: NeuroObserveTargetRequest = { generate: true },
): Promise<NeuroAcceptedJob> {
  return unwrap(
    client.openapi.POST('/api/neuro-commenting/campaigns/{campaign_id}/targets/{target_id}/observe', {
      params: { path: { campaign_id: campaignId, target_id: targetId } },
      body: payload,
    }),
    'observe neuro target',
  )
}

export async function refreshNeuroTargetMetadata(
  client: StylistTgClient,
  campaignId: string,
  targetId: string,
): Promise<NeuroAcceptedJob> {
  return unwrap(
    client.openapi.POST('/api/neuro-commenting/campaigns/{campaign_id}/targets/{target_id}/refresh-metadata', {
      params: { path: { campaign_id: campaignId, target_id: targetId } },
    }),
    'refresh neuro target metadata',
  )
}

export async function generateNeuroObservedPost(
  client: StylistTgClient,
  observedPostId: string,
  payload: NeuroGenerateObservedPostRequest = { force: false },
): Promise<NeuroAcceptedJob> {
  return unwrap(
    client.openapi.POST('/api/neuro-commenting/observed-posts/{observed_post_id}/generate', {
      params: { path: { observed_post_id: observedPostId } },
      body: payload,
    }),
    'generate neuro observed post',
  )
}

export async function resolveNeuroObservedPostDiscussion(
  client: StylistTgClient,
  observedPostId: string,
): Promise<NeuroObservedPost> {
  return client.request<NeuroObservedPost>(
    `/api/neuro-commenting/observed-posts/${encodeURIComponent(observedPostId)}/resolve-discussion`,
    { method: 'POST' },
  )
}
