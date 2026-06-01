import { useMutation, useQueryClient } from '@tanstack/react-query'

import { invalidateAccountSafetyQueries } from '@/lib/queries'

import { createAccountUpdateJob, type FormPayload } from './api'

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
