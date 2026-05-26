import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'

import { queryKeys } from '@/lib/queries'

import { SafetyGateBanner } from './SafetyGateBanner'

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api')
  return { ...actual, fetchAccountSafetyGate: vi.fn() }
})

function renderBanner(severity: 'ok' | 'warning' | 'blocked'): string {
  const queryClient = new QueryClient()
  queryClient.setQueryData(queryKeys.accountSafety.gate('account-1', 'commenting'), {
    account_id: 'account-1',
    intent: 'commenting',
    eligible: severity !== 'blocked',
    severity,
    reasons:
      severity === 'ok'
        ? []
        : [
            {
              code: severity === 'blocked' ? 'active_quarantine' : 'ip_change_cooldown',
              severity: severity === 'blocked' ? 'blocked' : 'warning',
              message: severity === 'blocked' ? 'Account has an active quarantine.' : 'Account is cooling down.',
              metadata: { source: 'test' },
            },
          ],
    ggr_score: 8,
    checked_at: '2026-05-20T08:00:00Z',
    cache_ttl_seconds: 60,
  })

  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <SafetyGateBanner accountId="account-1" intent="commenting" />
    </QueryClientProvider>,
  )
}

describe('SafetyGateBanner', () => {
  it('renders blocked verdicts', () => {
    const html = renderBanner('blocked')

    expect(html).toContain('Account safety blocked')
    expect(html).toContain('border-destructive/20')
  })

  it('renders warning verdicts', () => {
    const html = renderBanner('warning')

    expect(html).toContain('Account safety warning')
    expect(html).toContain('border-border')
  })

  it('returns null for ok verdicts', () => {
    const html = renderBanner('ok')

    expect(html).toBe('')
  })
})
