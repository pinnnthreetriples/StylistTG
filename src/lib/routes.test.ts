import { describe, expect, it } from 'vitest'

import {
  accountDebugRoute,
  accountJobsRoute,
  accountListRoute,
  accountMusicRoute,
  accountProfileRoute,
  accountRoute,
  accountStoriesRoute,
  accountWorkspaceRoute,
  appRoutes,
  resolveLegacyQueryRoute,
} from '@/lib/routes'

describe('app route contracts', () => {
  it('keeps canonical top-level URL contracts stable', () => {
    expect(accountListRoute()).toBe('/')
    expect(appRoutes.accounts()).toBe('/')
    expect(appRoutes.settings()).toBe('/settings')
    expect(appRoutes.authBatch()).toBe('/auth/batch')
  })

  it('keeps canonical account workspace URL contracts stable', () => {
    expect(accountRoute('account 1')).toBe('/accounts/account%201')
    expect(accountProfileRoute('account 1')).toBe('/accounts/account%201/profile')
    expect(accountJobsRoute('account/1')).toBe('/accounts/account%2F1/jobs')
    expect(accountStoriesRoute('account/1')).toBe('/accounts/account%2F1/stories')
    expect(accountMusicRoute('account/1')).toBe('/accounts/account%2F1/music')
    expect(accountDebugRoute('account/1')).toBe('/accounts/account%2F1/debug')
    expect(appRoutes.accountProfile('account/1')).toBe('/accounts/account%2F1/profile')
  })

  it('maps account workspace sections to canonical routes', () => {
    expect(accountWorkspaceRoute('account-1', 'profile')).toBe('/accounts/account-1/profile')
    expect(accountWorkspaceRoute('account-1', 'jobs')).toBe('/accounts/account-1/jobs')
    expect(accountWorkspaceRoute('account-1', 'stories')).toBe('/accounts/account-1/stories')
    expect(accountWorkspaceRoute('account-1', 'music')).toBe('/accounts/account-1/music')
    expect(accountWorkspaceRoute('account-1', 'debug')).toBe('/accounts/account-1/debug')
  })

  it('centralizes legacy query URL compatibility', () => {
    expect(resolveLegacyQueryRoute('?view=settings')).toBe('/settings')
    expect(resolveLegacyQueryRoute('?view=auth-batch')).toBe('/auth/batch')
    expect(resolveLegacyQueryRoute('?account_id=account 1')).toBe('/accounts/account%201')
    expect(resolveLegacyQueryRoute('?tab=profile')).toBeNull()
  })
})
