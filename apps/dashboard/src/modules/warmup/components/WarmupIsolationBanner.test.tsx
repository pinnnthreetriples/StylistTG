import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, test } from 'vitest'

import { warmupQueryKeys } from '../hooks'
import type { WarmupIsolationStatus } from '../types'

import { WarmupIsolationBanner } from './WarmupIsolationBanner'

function renderBanner(status: WarmupIsolationStatus, accountId = 'account-1'): string {
  const queryClient = new QueryClient()
  queryClient.setQueryData(warmupQueryKeys.isolation(accountId), status)
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <WarmupIsolationBanner accountId={accountId} />
    </QueryClientProvider>,
  )
}

describe('WarmupIsolationBanner', () => {
  test('renders nothing when account is not isolated', () => {
    const html = renderBanner({ is_isolated: false, claim: null })
    expect(html).toBe('')
  })

  test('renders the cross-module guard message and claim metadata when isolated', () => {
    const html = renderBanner({
      is_isolated: true,
      claim: {
        account_id: 'account-1',
        workspace_id: 'workspace-1',
        held_by: 'warmup:session-42',
        reason: 'warmup execution_mode=shadow',
        acquired_at: '2026-06-01T08:30:00Z',
      },
    })

    expect(html).toContain('Аккаунт сейчас занят прогревом')
    expect(html).toContain('warmup:session-42')
    expect(html).toContain('warmup execution_mode=shadow')
    // banner must call out cross-module guard meaning explicitly
    expect(html).toMatch(/Кампании|Рассылки|Парсинг/i)
  })
})
