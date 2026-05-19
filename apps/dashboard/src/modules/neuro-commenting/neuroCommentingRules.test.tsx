import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, test } from 'vitest'

import { ChannelRulesSection } from './components/ChannelRulesSection'
import { TargetsSection } from './components/TargetsSection'
import type { NeuroChannelRule } from './types'

const rules: NeuroChannelRule[] = [
  {
    id: 'rule-1',
    workspace_id: 'workspace-1',
    target_ref: '@blocked',
    rule_type: 'blacklist',
    reason: 'manual',
    created_by: 'user-1',
    created_at: '2026-05-19T10:00:00Z',
  },
  {
    id: 'rule-2',
    workspace_id: 'workspace-1',
    target_ref: '@suggested',
    rule_type: 'auto_whitelist_suggested',
    reason: 'health',
    created_by: null,
    created_at: '2026-05-19T10:00:00Z',
  },
]

describe('NeuroCommenting rules UI', () => {
  test('renders active rules and auto suggestions', () => {
    const html = renderToStaticMarkup(<ChannelRulesSection rules={rules} />)

    expect(html).toContain('@blocked')
    expect(html).toContain('blacklist')
    expect(html).toContain('@suggested')
    expect(html).toContain('suggested')
  })

  test('renders target rule action buttons', () => {
    const html = renderToStaticMarkup(
      <TargetsSection targets={[{ id: 'target-1', channel_ref: '@target', status: 'active' }]} />,
    )

    expect(html).toContain('Pause')
    expect(html).toContain('Resume')
    expect(html).toContain('Blacklist')
    expect(html).toContain('Whitelist')
  })
})
