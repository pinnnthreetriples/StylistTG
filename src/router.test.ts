import { describe, expect, it } from 'vitest'

import { router } from '@/router'

describe('TanStack Router route tree', () => {
  it('registers every canonical route path', () => {
    const routesByPath = Object.keys(router.routesByPath)

    expect(routesByPath).toEqual(
      expect.arrayContaining([
        '/',
        '/settings',
        '/auth/batch',
        '/accounts/$accountId',
        '/accounts/$accountId/profile',
        '/accounts/$accountId/jobs',
        '/accounts/$accountId/stories',
        '/accounts/$accountId/music',
        '/accounts/$accountId/debug',
      ]),
    )
  })

  it('uses product route fallback components for cold load and loader errors', () => {
    expect(router.options.defaultPendingComponent).toBeDefined()
    expect(router.options.defaultErrorComponent).toBeDefined()
    expect(router.options.defaultPendingMs).toBe(600)
  })
})
