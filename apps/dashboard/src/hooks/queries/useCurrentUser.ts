import { useQuery } from '@tanstack/react-query'

import { currentUserQueryOptions } from '@/lib/queries'

export function useCurrentUser() {
  return useQuery(currentUserQueryOptions())
}
