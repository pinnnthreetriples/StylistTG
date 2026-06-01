import { unwrap } from './core'
import type { JobSummary, ProfilePreview, Schema, StylistTgClient } from './types'
export async function previewProfileJob(
  client: StylistTgClient,
  payload: Schema<'ProfilePreviewRequest'>,
): Promise<ProfilePreview> {
  return unwrap(client.openapi.POST('/api/jobs/profile/preview', { body: payload }), 'profile preview')
}

export async function previewAccountUpdateJob(
  client: StylistTgClient,
  payload: Schema<'AccountUpdateCreate'>,
  init?: RequestInit,
): Promise<ProfilePreview> {
  return client.request<ProfilePreview>('/api/account-update/preview', {
    ...init,
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function createProfileJob(
  client: StylistTgClient,
  payload: Schema<'ProfileJobCreate'>,
): Promise<JobSummary> {
  return unwrap(client.openapi.POST('/api/jobs/profile', { body: payload }), 'profile job')
}

export async function createAccountUpdateJob(
  client: StylistTgClient,
  payload: Schema<'AccountUpdateCreate'>,
): Promise<JobSummary> {
  return client.request<JobSummary>('/api/account-update/jobs', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}
