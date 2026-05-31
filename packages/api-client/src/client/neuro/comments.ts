import { unwrap } from '../core'
import type {
  NeuroGeneratedComment,
  NeuroGeneratedCommentPage,
  NeuroGeneratedCommentReject,
  NeuroGeneratedCommentUpdate,
  NeuroManualSend,
  NeuroManualSendRequest,
  StylistTgClient,
} from '../types'
export async function fetchNeuroGeneratedComments(
  client: StylistTgClient,
  params?: { campaign_id?: string; page?: number; limit?: number },
): Promise<NeuroGeneratedCommentPage> {
  return unwrap(
    client.openapi.GET('/api/neuro-commenting/generated-comments', {
      params: { query: params },
    }),
    'neuro generated comments',
  )
}

export async function fetchNeuroGeneratedComment(
  client: StylistTgClient,
  commentId: string,
): Promise<NeuroGeneratedComment> {
  return unwrap(
    client.openapi.GET('/api/neuro-commenting/generated-comments/{comment_id}', {
      params: { path: { comment_id: commentId } },
    }),
    'neuro generated comment',
  )
}

export async function editNeuroGeneratedComment(
  client: StylistTgClient,
  commentId: string,
  payload: NeuroGeneratedCommentUpdate,
): Promise<NeuroGeneratedComment> {
  return unwrap(
    client.openapi.PATCH('/api/neuro-commenting/generated-comments/{comment_id}', {
      params: { path: { comment_id: commentId } },
      body: payload,
    }),
    'edit neuro generated comment',
  )
}

export async function approveNeuroGeneratedComment(
  client: StylistTgClient,
  commentId: string,
): Promise<NeuroGeneratedComment> {
  return unwrap(
    client.openapi.POST('/api/neuro-commenting/generated-comments/{comment_id}/approve', {
      params: { path: { comment_id: commentId } },
    }),
    'approve neuro generated comment',
  )
}

export async function rejectNeuroGeneratedComment(
  client: StylistTgClient,
  commentId: string,
  payload: NeuroGeneratedCommentReject,
): Promise<NeuroGeneratedComment> {
  return unwrap(
    client.openapi.POST('/api/neuro-commenting/generated-comments/{comment_id}/reject', {
      params: { path: { comment_id: commentId } },
      body: payload,
    }),
    'reject neuro generated comment',
  )
}

export async function sendNeuroGeneratedComment(
  client: StylistTgClient,
  commentId: string,
  payload: NeuroManualSendRequest = { enqueue: true },
): Promise<NeuroManualSend> {
  return unwrap(
    client.openapi.POST('/api/neuro-commenting/generated-comments/{comment_id}/send', {
      params: { path: { comment_id: commentId } },
      body: payload,
    }),
    'send neuro generated comment',
  )
}
