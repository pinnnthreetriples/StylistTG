import { afterEach, describe, expect, it, vi } from 'vitest'

import { isLocalE2EAuthBypassEnabled } from './supabase'

function stubWindow(hostname: string, enabled: boolean) {
  vi.stubGlobal('window', {
    location: { hostname },
    localStorage: {
      getItem: (key: string) => (key === 'stylisttg:e2e-auth-bypass' && enabled ? 'true' : null),
    },
  })
}

describe('isLocalE2EAuthBypassEnabled', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('allows the bypass only on localhost hosts', () => {
    stubWindow('localhost', true)
    expect(isLocalE2EAuthBypassEnabled()).toBe(true)

    stubWindow('127.0.0.1', true)
    expect(isLocalE2EAuthBypassEnabled()).toBe(true)

    stubWindow('dashboard.example.com', true)
    expect(isLocalE2EAuthBypassEnabled()).toBe(false)
  })
})
