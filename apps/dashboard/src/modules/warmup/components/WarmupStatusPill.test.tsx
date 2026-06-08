import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, test } from 'vitest'

import { WarmupStatusPill } from './WarmupStatusPill'
import { resolveWarmupModuleStatus } from './WarmupStatusPillModel'

describe('WarmupStatusPill', () => {
  test.each(['STOPPED', 'RUNNING', 'OFFLINE', 'LIVE'] as const)('%s snapshot', (status) => {
    expect(
      renderToStaticMarkup(
        <WarmupStatusPill
          status={status}
          lastHeartbeatAt="2026-06-05T10:00:00Z"
          now={new Date('2026-06-05T10:00:10Z')}
        />,
      ),
    ).toMatchSnapshot()
  })

  test('resolves stale heartbeat to offline after 30 seconds', () => {
    expect(
      resolveWarmupModuleStatus({
        status: 'LIVE',
        lastHeartbeatAt: '2026-06-05T10:00:00Z',
        now: new Date('2026-06-05T10:00:31Z'),
      }),
    ).toBe('OFFLINE')
  })

  test('switches label when status prop changes', () => {
    const running = renderToStaticMarkup(<WarmupStatusPill status="RUNNING" />)
    const stopped = renderToStaticMarkup(<WarmupStatusPill status="STOPPED" />)

    expect(running).toContain('Работает')
    expect(stopped).toContain('Остановлено')
    expect(running).not.toEqual(stopped)
  })
})
