import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, test } from 'vitest'

import { VirtualJobLogList } from '@/features/jobs/VirtualJobLogList'
import { createDemoJobLogRows } from '@/features/jobs/jobLogModel'

describe('VirtualJobLogList', () => {
  test('creates a large read-only demo log set', () => {
    expect(createDemoJobLogRows(1000)).toHaveLength(1000)
  })

  test('renders a large list without a browser crash', () => {
    const html = renderToStaticMarkup(<VirtualJobLogList entries={createDemoJobLogRows(1000)} />)

    expect(html).toContain('Служебное событие воркера 1')
  })
})
