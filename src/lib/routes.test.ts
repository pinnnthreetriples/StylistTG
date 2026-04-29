import { describe, expect, it } from 'vitest'

import { accountListRoute, accountProfileRoute, appRoutes } from '@/lib/routes'

describe('app route contracts', () => {
  it('keeps current top-level URL contracts stable', () => {
    expect(accountListRoute()).toBe('/')
    expect(appRoutes.accounts()).toBe('/')
    expect(appRoutes.settings()).toBe('/?view=settings')
    expect(appRoutes.authBatch()).toBe('/?view=auth-batch')
  })

  it('encodes account profile routes through the existing account_id search param', () => {
    expect(accountProfileRoute('account 1')).toBe('/?account_id=account%201')
    expect(appRoutes.accountProfile('account/1')).toBe('/?account_id=account%2F1')
  })
})
