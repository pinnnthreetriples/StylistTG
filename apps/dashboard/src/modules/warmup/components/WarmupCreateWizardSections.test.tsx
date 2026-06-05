import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, test } from 'vitest'

import type { WarmupValidateResponse } from '../types'
import { WarmupValidationPanel } from './WarmupCreateWizardSections'

describe('WarmupValidationPanel', () => {
  test('renders proxy adaptation warning for mobile proxy', () => {
    const html = renderToStaticMarkup(
      <WarmupValidationPanel
        validation={{
          blocking_reasons: [],
          checks: [],
          is_ready: true,
          proxy_adaptation: {
            applied_preset: 'economic',
            disabled_actions: ['watch_video', 'listen_voice'],
            proxy_category: 'mobile',
          },
          warnings: [],
        }}
      />,
    )

    expect(html).toContain('Применён preset: economic из-за mobile proxy')
    expect(html).toContain('watch video')
    expect(html).toContain('listen voice')
  })

  test('renders full preset when datacenter proxy keeps actions enabled', () => {
    const validation: WarmupValidateResponse = {
      blocking_reasons: [],
      checks: [],
      is_ready: true,
      proxy_adaptation: {
        applied_preset: 'full',
        disabled_actions: [],
        proxy_category: 'datacenter',
      },
      warnings: [],
    }

    const html = renderToStaticMarkup(<WarmupValidationPanel validation={validation} />)

    expect(html).toContain('Применён preset: full из-за datacenter proxy')
  })
})
