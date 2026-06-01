import { useMutation, useQueryClient } from '@tanstack/react-query'

import {
  deleteStoryPost,
  refreshRuntime,
} from '@/lib/api'
import { invalidateAccountSafetyQueries } from '@/lib/queries'
// fallow-ignore-next-line unused-export
export { useCreateAccountUpdateJobMutation } from '@/modules/account-editing/mutationHooks'

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
