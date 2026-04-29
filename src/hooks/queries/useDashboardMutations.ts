import { useMutation } from '@tanstack/react-query'

import {
  createAccountUpdateJob,
  deleteStoryPost,
  refreshRuntime,
  type FormPayload,
} from '@/lib/api'

export function useRefreshRuntimeMutation() {
  return useMutation({
    mutationFn: refreshRuntime,
  })
}

export function useDeleteStoryPostMutation() {
  return useMutation({
    mutationFn: ({ accountId, postId }: { accountId: string; postId: string }) =>
      deleteStoryPost(accountId, postId),
  })
}

export function useCreateAccountUpdateJobMutation() {
  return useMutation({
    mutationFn: ({ accountId, form }: { accountId: string; form: FormPayload }) =>
      createAccountUpdateJob(accountId, form),
  })
}
