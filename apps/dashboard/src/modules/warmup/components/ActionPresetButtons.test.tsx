import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, test, vi } from 'vitest'

import { ActionPresetButtons } from './ActionPresetButtons'

vi.mock('../hooks', () => ({
  useApplyWarmupActionPreset: () => ({
    mutate: vi.fn(),
    isPending: false,
    error: null,
  }),
}))

describe('ActionPresetButtons', () => {
  test('renders the three warmup action presets', () => {
    const html = renderToStaticMarkup(<ActionPresetButtons strategyId="strategy-1" />)
    const buttonLabels = Array.from(html.matchAll(/>([^<>]+)<\/button>/g), (match) => match[1])

    expect(html).toContain('Тонкая настройка')
    expect(buttonLabels).toMatchInlineSnapshot(`
      [
        "Экономный режим",
        "Включить всё",
        "Выключить всё",
      ]
    `)
  })
})
