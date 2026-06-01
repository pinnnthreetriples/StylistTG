import { accountHeader, headersToObject, unwrap } from './core'
import type { StoryCapabilities, StoryDraftCreate, StoryDraftRead, StoryDraftUpdate, StylistTgClient } from './types'
export async function fetchStoryDrafts(client: StylistTgClient, accountId: string): Promise<StoryDraftRead[]> {
  return unwrap(
    client.openapi.GET('/api/story-drafts/{account_id}', {
      params: { path: { account_id: accountId } },
    }),
    'story drafts',
  )
}

export async function fetchStoryCapabilities(client: StylistTgClient, accountId: string): Promise<StoryCapabilities> {
  return unwrap(
    client.openapi.GET('/api/story-capabilities/{account_id}', {
      params: { path: { account_id: accountId } },
    }),
    'story capabilities',
  )
}

export async function createStoryDraft(
  client: StylistTgClient,
  draft: StoryDraftCreate,
): Promise<StoryDraftRead> {
  return unwrap(client.openapi.POST('/api/story-drafts', { body: draft }), 'create story draft')
}

export async function updateStoryDraft(
  client: StylistTgClient,
  draftId: string,
  patch: StoryDraftUpdate,
): Promise<StoryDraftRead> {
  return unwrap(
    client.openapi.PATCH('/api/story-drafts/{draft_id}', {
      params: { path: { draft_id: draftId } },
      body: patch,
    }),
    'update story draft',
  )
}

export async function deleteStoryDraft(client: StylistTgClient, draftId: string): Promise<void> {
  await client.request<void>(`/api/story-drafts/${encodeURIComponent(draftId)}`, { method: 'DELETE' })
}

export async function deleteStoryPost(
  client: StylistTgClient,
  accountId: string,
  postId: string,
  init?: RequestInit,
): Promise<void> {
  await client.request<void>(`/api/story-posts/${encodeURIComponent(postId)}`, {
    ...init,
    method: 'DELETE',
    headers: { ...headersToObject(init?.headers), ...accountHeader(accountId) },
  })
}

export function buildAssetContentUrl(client: StylistTgClient, assetId: string): string {
  return client.buildUrl(`/api/assets/${encodeURIComponent(assetId)}/content`)
}

export async function uploadAsset(client: StylistTgClient, path: string, file: File): Promise<{ id: string }> {
  const body = new FormData()
  body.append('file', file)
  return client.request<{ id: string }>(path, { method: 'POST', body })
}
