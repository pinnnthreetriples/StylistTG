import { useMutation, useQueryClient } from '@tanstack/react-query'

import {
  createAccountUpdateJob,
  deleteStoryPost,
  refreshRuntime,
  type FormPayload,
} from '@/lib/api'
import { invalidateAccountSafetyQueries } from '@/lib/queries'

export function useRefreshRuntimeMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: refreshRuntime,
    onSuccess: (_result, accountId) => {
      invalidateAccountSafetyQueries(queryClient, accountId)
    },
  })
}

export function useDeleteStoryPostMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ accountId, postId }: { accountId: string; postId: string }) =>
      deleteStoryPost(accountId, postId),
    onSuccess: (_result, variables) => {
      invalidateAccountSafetyQueries(queryClient, variables.accountId)
    },
  })
}

export function useCreateAccountUpdateJobMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ accountId, form }: { accountId: string; form: FormPayload }) =>
      createAccountUpdateJob(accountId, form),
    onSuccess: (_result, variables) => {
      invalidateAccountSafetyQueries(queryClient, variables.accountId)
    },
  })
}
