import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, test } from 'vitest'

import { GGRBadge } from './GGRBadge'

describe('GGRBadge', () => {
  test('renders green badge for strong bucket', () => {
    const html = renderToStaticMarkup(<GGRBadge score={8.5} bucket="strong" />)
    expect(html).toContain('8.5')
    expect(html).toContain('emerald')
  })

  test('renders amber badge for medium bucket', () => {
    const html = renderToStaticMarkup(<GGRBadge score={5.2} bucket="medium" />)
    expect(html).toContain('5.2')
    expect(html).toContain('amber')
  })

  test('renders red badge for weak bucket', () => {
    const html = renderToStaticMarkup(<GGRBadge score={2.1} bucket="weak" />)
    expect(html).toContain('2.1')
    expect(html).toContain('red')
  })
})
