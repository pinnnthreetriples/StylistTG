import { QueryClient } from '@tanstack/react-query'
import { describe, expect, it, vi } from 'vitest'

import { queryClient } from '@/lib/queryClient'
import {
  accountsQueryOptions,
  accountSafetyQueryOptions,
  accountSafetySummaryQueryOptions,
  accountBatchSafetyPreviewQueryOptions,
  accountValidityChecksQueryOptions,
  authStateQueryOptions,
  dashboardBundleQueryOptions,
  dashboardProfileQueryOptions,
  fetchDashboardBundleQuery,
  fetchJobStateQuery,
  getCachedDashboardBundle,
  jobDetailQueryOptions,
  jobStepsQueryOptions,
  latestJobQueryOptions,
  latestJobsQueryOptions,
  removeAccountSafetyFromCache,
  queryKeys,
  removeAccountFromAccountsCache,
  removeAccountScopedQueries,
  settingsBundleQueryOptions,
  storyCapabilitiesQueryOptions,
  storyDraftsQueryOptions,
  updateSettingsAuthModeInCache,
  updateAccountSafetyAfterValidityCheck,
  updateSettingsPolicyInCache,
  type DashboardBundle,
  type SettingsBundle,
} from '@/lib/queries'

describe('query cache configuration', () => {
  it('keeps server state warm long enough for fast tab navigation', () => {
    expect(queryClient.getDefaultOptions().queries).toMatchObject({
      staleTime: 30_000,
      gcTime: 20 * 60_000,
      refetchOnWindowFocus: false,
      retry: 1,
    })
  })

  it('uses stable query keys for settings, accounts and dashboard tabs', () => {
    expect(accountsQueryOptions().queryKey).toEqual(queryKeys.accounts)
    expect(accountSafetySummaryQueryOptions().queryKey).toEqual(['accountSafety', 'summary'])
    expect(accountSafetyQueryOptions('account-1').queryKey).toEqual(['accountSafety', 'account-1'])
    expect(accountValidityChecksQueryOptions('account-1').queryKey).toEqual(['accountSafety', 'account-1', 'checks'])
    expect(accountBatchSafetyPreviewQueryOptions(['account-2', 'account-1'], 'profile_update').queryKey).toEqual([
      'accountSafety',
      'batchPreview',
      'profile_update',
      'account-1,account-2',
      false,
    ])
    expect(accountBatchSafetyPreviewQueryOptions(['account-1'], 'profile_update', true).queryKey).toEqual([
      'accountSafety',
      'batchPreview',
      'profile_update',
      'account-1',
      true,
    ])
    expect(authStateQueryOptions('account-1').queryKey).toEqual(['authState', 'account-1'])
    expect(settingsBundleQueryOptions().queryKey).toEqual(['settings', 'bundle'])
    expect(dashboardBundleQueryOptions('account-1').queryKey).toEqual([
      'dashboard',
      'account-1',
      'bundle',
    ])
    expect(dashboardProfileQueryOptions('account-1').queryKey).toEqual([
      'dashboard',
      'account-1',
      'profile',
    ])
    expect(latestJobsQueryOptions('account-1').queryKey).toEqual([
      'dashboard',
      'account-1',
      'jobs',
    ])
    expect(latestJobQueryOptions('account-1').queryKey).toEqual([
      'dashboard',
      'account-1',
      'latestJob',
    ])
    expect(jobDetailQueryOptions('job-1').queryKey).toEqual(['job', 'job-1'])
    expect(jobStepsQueryOptions('job-1').queryKey).toEqual(['job', 'job-1', 'steps'])
    expect(queryKeys.job.stateBundle('job-1')).toEqual(['job', 'job-1', 'stateBundle'])
  })

  it('keeps dashboard sub-resource keys under the account prefix for future pages', () => {
    const accountPrefix = queryKeys.dashboard.account('account-1')

    expect(dashboardProfileQueryOptions('account-1').queryKey.slice(0, 2)).toEqual(accountPrefix)
    expect(latestJobsQueryOptions('account-1').queryKey.slice(0, 2)).toEqual(accountPrefix)
    expect(storyDraftsQueryOptions('account-1').queryKey.slice(0, 2)).toEqual(accountPrefix)
    expect(storyCapabilitiesQueryOptions('account-1').queryKey.slice(0, 2)).toEqual(accountPrefix)
  })

  it('can force dashboard bundle refresh even while cached data is fresh', async () => {
    const client = new QueryClient({
      defaultOptions: {
        queries: {
          staleTime: 30_000,
          retry: false,
        },
      },
    })
    let calls = 0
    const first = {
      dashboard: { version: 1 },
      jobs: [],
      storyDrafts: [],
      storyCapabilities: { stories_enabled: true },
    } as unknown as DashboardBundle
    const second = {
      dashboard: { version: 2 },
      jobs: [],
      storyDrafts: [],
      storyCapabilities: { stories_enabled: true },
    } as unknown as DashboardBundle
    const queryFn = vi.fn(async () => {
      calls += 1
      return calls === 1 ? first : second
    })

    await client.fetchQuery({
      queryKey: queryKeys.dashboard.bundle('account-1'),
      queryFn,
    })

    const cached = await fetchDashboardBundleQuery(client, 'account-1', {
      queryFn,
    })
    expect(cached).toBe(first)

    const refreshed = await fetchDashboardBundleQuery(client, 'account-1', {
      forceRefresh: true,
      queryFn,
    })
    expect(refreshed).toBe(second)
    expect(queryFn).toHaveBeenCalledTimes(2)
  })

  it('exposes cache helpers for account-scoped dashboard data', () => {
    const client = new QueryClient()
    const bundle = {
      dashboard: { account: { account_id: 'account-1' } },
      jobs: [],
      storyDrafts: [],
      storyCapabilities: { stories_enabled: true },
    } as unknown as DashboardBundle
    client.setQueryData(queryKeys.dashboard.bundle('account-1'), bundle)
    client.setQueryData(queryKeys.authState('account-1'), { account_id: 'account-1' })

    expect(getCachedDashboardBundle(client, 'account-1')).toBe(bundle)

    removeAccountScopedQueries(client, 'account-1')

    expect(client.getQueryData(queryKeys.dashboard.bundle('account-1'))).toBeUndefined()
    expect(client.getQueryData(queryKeys.authState('account-1'))).toBeUndefined()
  })

  it('updates settings bundle cache through domain helpers', () => {
    const client = new QueryClient()
    const bundle = {
      runtime: {},
      preflight: {},
      policy: { profile_job_cooldown_seconds: 30 },
      authMode: { tdlib_use_test_dc: false },
    } as unknown as SettingsBundle
    const policy = { profile_job_cooldown_seconds: 60 } as SettingsBundle['policy']
    const authMode = { tdlib_use_test_dc: true } as SettingsBundle['authMode']
    client.setQueryData(queryKeys.settings.bundle, bundle)

    updateSettingsPolicyInCache(client, policy)
    updateSettingsAuthModeInCache(client, authMode)

    expect(client.getQueryData<SettingsBundle>(queryKeys.settings.bundle)).toMatchObject({
      policy,
      authMode,
    })
  })

  it('removes deleted accounts from account list cache', () => {
    const client = new QueryClient()
    client.setQueryData(queryKeys.accounts, [
      { account_id: 'account-1' },
      { account_id: 'account-2' },
    ])

    removeAccountFromAccountsCache(client, 'account-1')

    expect(client.getQueryData(queryKeys.accounts)).toEqual([{ account_id: 'account-2' }])
  })

  it('removes deleted account safety from account and summary caches', () => {
    const client = new QueryClient()
    client.setQueryData(queryKeys.accountSafety.account('account-1'), { account_id: 'account-1' })
    client.setQueryData(queryKeys.accountSafety.summary, [
      { account_id: 'account-1' },
      { account_id: 'account-2' },
    ])

    removeAccountSafetyFromCache(client, 'account-1')

    expect(client.getQueryData(queryKeys.accountSafety.account('account-1'))).toBeUndefined()
    expect(client.getQueryData(queryKeys.accountSafety.summary)).toEqual([{ account_id: 'account-2' }])
  })

  it('updates account safety cache immediately after validity check', () => {
    const client = new QueryClient()
    const check = {
      id: 'check-1',
      account_id: 'account-1',
      mode: 'tdlib_readonly',
      status: 'completed',
      started_at: '2026-04-30T10:00:00Z',
      finished_at: '2026-04-30T10:00:01Z',
      error_code: null,
      error_class: null,
      details: null,
      result: { validity_status: 'valid' },
      created_at: '2026-04-30T10:00:00Z',
    }
    client.setQueryData(queryKeys.accountSafety.account('account-1'), {
      account_id: 'account-1',
      validity_status: 'db_snapshot',
      last_validity_check: {
        ...check,
        id: 'old-check',
        finished_at: '2026-04-30T07:00:00Z',
      },
    })
    client.setQueryData(queryKeys.accountSafety.checks('account-1'), [{ ...check, id: 'old-check' }])

    updateAccountSafetyAfterValidityCheck(client, 'account-1', check)

    expect(client.getQueryData(queryKeys.accountSafety.account('account-1'))).toMatchObject({
      validity_status: 'valid',
      last_validity_check: check,
    })
    expect(client.getQueryData(queryKeys.accountSafety.checks('account-1'))).toEqual([check, { ...check, id: 'old-check' }])
  })

  it('fetches job state through query cache helpers and accepts preloaded dashboard data', async () => {
    const client = new QueryClient()
    const job = { job_id: 'job-1', job_state: 'running' } as unknown as Awaited<ReturnType<typeof fetchJobStateQuery>>['job']
    const steps = [{ step_key: 'set_name' }] as unknown as Awaited<ReturnType<typeof fetchJobStateQuery>>['steps']
    const latestJob = { job_id: 'job-1', job_state: 'running' } as unknown as Awaited<ReturnType<typeof fetchJobStateQuery>>['latestJob']
    const jobs = [latestJob]
    const queryFn = vi.fn(async () => ({ job, steps }))

    const result = await fetchJobStateQuery(client, 'account-1', 'job-1', {
      latestJob,
      jobs,
      queryFn,
    })

    expect(result).toEqual({ job, steps, latestJob, jobs })
    expect(queryFn).toHaveBeenCalledTimes(1)
    expect(client.getQueryData(queryKeys.job.detail('job-1'))).toBe(job)
    expect(client.getQueryData(queryKeys.job.steps('job-1'))).toBe(steps)
  })
})
