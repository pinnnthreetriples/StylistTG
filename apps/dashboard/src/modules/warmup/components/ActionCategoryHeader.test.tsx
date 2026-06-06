import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, test } from 'vitest'

import { TRAFFIC_TOOLTIP } from '../labels'
import { ActionCategoryHeader } from './ActionCategoryHeader'

describe('ActionCategoryHeader', () => {
  test('renders traffic badge for traffic-heavy categories', () => {
    const html = renderToStaticMarkup(
      <ActionCategoryHeader category="entertainment" trafficHeavy />,
    )

    expect(html).toContain('Развлечения')
    expect(html).toContain('трафик')
    expect(html).toContain(TRAFFIC_TOOLTIP)
  })

  test('renders category without traffic badge when category is light', () => {
    const html = renderToStaticMarkup(
      <ActionCategoryHeader category="social" trafficHeavy={false} />,
    )

    expect(html).toContain('Социальные')
    expect(html).not.toContain('трафик')
  })
})
