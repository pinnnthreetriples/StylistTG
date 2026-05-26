import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, test } from 'vitest'

import { GGRBadge } from './GGRBadge'

describe('GGRBadge', () => {
  test('renders strong bucket label and score', () => {
    const html = renderToStaticMarkup(<GGRBadge score={8.5} bucket="strong" />)
    expect(html).toContain('8.5')
    expect(html).toContain('Сильный')
  })

  test('renders medium bucket label and score', () => {
    const html = renderToStaticMarkup(<GGRBadge score={5.2} bucket="medium" />)
    expect(html).toContain('5.2')
    expect(html).toContain('Средний')
  })

  test('renders weak bucket label and score', () => {
    const html = renderToStaticMarkup(<GGRBadge score={2.1} bucket="weak" />)
    expect(html).toContain('2.1')
    expect(html).toContain('Слабый')
  })
})
