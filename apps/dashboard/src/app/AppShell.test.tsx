import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, test } from 'vitest'

import { primaryNavigation } from '@/app/navigation'

describe('SaaS shell navigation', () => {
  test('defines the expected product zones', () => {
    expect(primaryNavigation.map((item) => item.label)).toEqual([
      'Accounts',
      'Health Center',
      'Jobs',
      'Proxy Center',
      'Settings',
      'Billing',
    ])
  })

  test('can render simple shell content without a browser', () => {
    const html = renderToStaticMarkup(<div data-shell="saas">Workspace: Staging Ops</div>)

    expect(html).toContain('Workspace: Staging Ops')
  })
})
