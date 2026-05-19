import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, test } from 'vitest'

import { LiveReadinessSection } from './components/LiveReadinessSection'
import { neuroQueryKeys } from './hooks'
import type { NeuroLiveReadiness } from './types'

function renderWithClient(ui: React.ReactElement, seed?: (queryClient: QueryClient) => void): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { refetchOnMount: false, retry: false } } })
  seed?.(queryClient)
  return renderToStaticMarkup(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>)
}

function readiness(overrides: Partial<NeuroLiveReadiness> = {}): NeuroLiveReadiness {
  return {
    campaign_id: 'campaign-1',
    ready: false,
    checks: [
      {
        code: 'DISCUSSION_MESSAGE_NOT_RESOLVED',
        severity: 'blocker',
        message: 'approved comments require resolved discussion messages before send',
      },
      {
        code: 'TDLIB_SEND_ENABLED',
        severity: 'info',
        message: 'TDLib neuro-comment sending flag is enabled',
      },
    ],
    ...overrides,
  }
}

describe('neuro-commenting live readiness', () => {
  test('query key is stable', () => {
    expect(neuroQueryKeys.liveReadiness('campaign-1')).toEqual([
      'neuro-commenting',
      'campaigns',
      'campaign-1',
      'live-readiness',
    ])
  })

  test('section renders blockers and not-ready state', () => {
    const html = renderWithClient(<LiveReadinessSection campaignId="campaign-1" />, (queryClient) => {
      queryClient.setQueryData(neuroQueryKeys.liveReadiness('campaign-1'), readiness())
    })

    expect(html).toContain('Live readiness')
    expect(html).toContain('Not ready')
    expect(html).toContain('DISCUSSION_MESSAGE_NOT_RESOLVED')
  })

  test('section renders ready state', () => {
    const html = renderWithClient(<LiveReadinessSection campaignId="campaign-1" />, (queryClient) => {
      queryClient.setQueryData(
        neuroQueryKeys.liveReadiness('campaign-1'),
        readiness({
          ready: true,
          checks: [{ code: 'REDIS_LIMITER_READY', severity: 'info', message: 'Redis limiter is ready' }],
        }),
      )
    })

    expect(html).toContain('Ready')
    expect(html).toContain('REDIS_LIMITER_READY')
  })
})
