import type { QueryClient } from '@tanstack/react-query'

import { queryKeys } from './queryKeys'
import {
  dashboardBundleQueryOptions,
  jobDetailQueryOptions,
  jobStepsQueryOptions,
  latestJobQueryOptions,
  latestJobsQueryOptions,
} from './queryOptions'
import type { DashboardBundle, JobStateBundle } from './queryTypes'

export function getCachedDashboardBundle(queryClient: QueryClient, accountId: string): DashboardBundle | undefined {
  return queryClient.getQueryData<DashboardBundle>(queryKeys.dashboard.bundle(accountId))
}

export async function fetchDashboardBundleQuery(
  queryClient: QueryClient,
  accountId: string,
  options?: {
    forceRefresh?: boolean
    queryFn?: () => Promise<DashboardBundle>
  },
): Promise<DashboardBundle> {
  const query = {
    ...dashboardBundleQueryOptions(accountId),
    ...(options?.queryFn ? { queryFn: options.queryFn } : {}),
    ...(options?.forceRefresh ? { staleTime: 0 } : {}),
  }
  return queryClient.fetchQuery(query)
}

export async function fetchJobStateQuery(
  queryClient: QueryClient,
  accountId: string,
  jobId: string,
  options?: {
    latestJob?: JobStateBundle['latestJob']
    jobs?: JobStateBundle['jobs']
    queryFn?: () => Promise<Pick<JobStateBundle, 'job' | 'steps'>>
  },
): Promise<JobStateBundle> {
  const [jobAndSteps, latestJob, jobs] = await Promise.all([
    options?.queryFn
      ? queryClient.fetchQuery({
          queryKey: queryKeys.job.stateBundle(jobId),
          queryFn: options.queryFn,
          staleTime: 0,
        })
      : Promise.all([
          queryClient.fetchQuery(jobDetailQueryOptions(jobId)),
          queryClient.fetchQuery(jobStepsQueryOptions(jobId)),
        ]).then(([job, steps]) => ({ job, steps })),
    options?.latestJob
      ? Promise.resolve(options.latestJob)
      : queryClient.fetchQuery(latestJobQueryOptions(accountId)),
    options?.jobs ? Promise.resolve(options.jobs) : queryClient.fetchQuery(latestJobsQueryOptions(accountId)),
  ])

  queryClient.setQueryData(queryKeys.job.detail(jobId), jobAndSteps.job)
  queryClient.setQueryData(queryKeys.job.steps(jobId), jobAndSteps.steps)
  return { job: jobAndSteps.job, steps: jobAndSteps.steps, latestJob, jobs }
}
