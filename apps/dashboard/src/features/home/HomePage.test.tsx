import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, test, vi } from 'vitest'

vi.mock('@tanstack/react-query', () => ({
  queryOptions: (options: unknown) => options,
  useQuery: vi.fn((options: { queryKey?: readonly unknown[] }) => {
    const key = options.queryKey?.join(':')
    if (key === 'accounts') return { data: [], isError: false, isLoading: false }
    if (key === 'accountRisk:summary') {
      return {
        data: {
          total: 0,
          low: 0,
          medium: 0,
          high: 0,
          critical: 0,
          reauth_required: 0,
          missing_session: 0,
          runtime_unhealthy: 0,
          proxy_problem: 0,
        },
        isError: false,
        isLoading: false,
      }
    }
    if (key === 'settings:frontendDiagnostics') {
      return {
        data: {
          db: { status: 'ok' },
          tdlib: {
            execution_plane_ready: false,
            live_enabled: false,
          },
        },
        isError: false,
      }
    }
    if (key === 'home:workers:queues') return { data: [], isError: false }
    if (key === 'home:ready') return { data: { status: 'ok' }, isError: false }
    return { data: undefined, isError: true, isLoading: false }
  }),
}))

vi.mock('@tanstack/react-router', () => ({
  Link: ({ children }: { children: React.ReactNode }) => <a>{children}</a>,
}))

vi.mock('@/components/ui/AnimatedPage', () => ({
  AnimatedPage: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}))

vi.mock('@/components/ui/AnimatedSection', () => ({
  AnimatedSection: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}))

import { HomePage } from './HomePage'

describe('HomePage worker status', () => {
  test('uses authenticated queue descriptors for the home worker badge', () => {
    const html = renderToStaticMarkup(<HomePage />)

    expect(html).toContain('Очереди (Worker)')
    expect(html).toContain('Настроены')
    expect(html).not.toContain('Недоступны')
  })
})
