import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, test } from 'vitest'

import type { WarmupActionMetadata } from '../types'
import {
  WarmupDisabledActionsToggle,
  groupActionMetadata,
  hasAtLeastOneEnabled,
  normalizeDisabledActions,
} from './WarmupDisabledActionsToggle'

const METADATA: WarmupActionMetadata[] = [
  {
    action_type: 'feed_read',
    category: 'reading',
    traffic_heavy: false,
    write_action: false,
    requires_premium: false,
  },
  {
    action_type: 'react_to_post',
    category: 'activity',
    traffic_heavy: false,
    write_action: true,
    requires_premium: false,
  },
]

describe('WarmupDisabledActionsToggle', () => {
  test('groups actions by category and normalizes unknown saved values', () => {
    const grouped = groupActionMetadata(METADATA)

    expect(grouped.reading?.map((item) => item.action_type)).toEqual(['feed_read'])
    expect(normalizeDisabledActions(['missing', 'react_to_post'], METADATA)).toEqual([
      'react_to_post',
    ])
  })

  test('guards against disabling every action', () => {
    expect(hasAtLeastOneEnabled(METADATA, ['feed_read'])).toBe(true)
    expect(hasAtLeastOneEnabled(METADATA, ['feed_read', 'react_to_post'])).toBe(false)
  })

  test('renders disabled action checkboxes', () => {
    const queryClient = new QueryClient()
    const html = renderToStaticMarkup(
      <QueryClientProvider client={queryClient}>
        <WarmupDisabledActionsToggle
          sessionId="session-1"
          disabledActions={['react_to_post']}
          metadata={METADATA}
        />
      </QueryClientProvider>,
    )

    expect(html).toContain('Отключённые действия')
    expect(html).toContain('feed read')
    expect(html).toContain('react to post')
    expect(html).toContain('checked=""')
  })
})
