import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, test, vi } from 'vitest'

import { SafetyPolicyPanel } from './SafetyPolicyPanel'

vi.mock('@tanstack/react-query', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@tanstack/react-query')>()
  return {
    ...actual,
    useMutation: () => ({
      mutate: vi.fn(),
      isPending: false,
      error: null,
    }),
    useQuery: () => ({
      data: {
        id: 'policy-1',
        workspace_id: 'workspace-1',
        mode: 'balanced',
        delay_multiplier: 1,
        typing_chars_per_minute_min: 100,
        typing_chars_per_minute_max: 150,
        profile_view_probability: 0.7,
        scroll_probability: 0.3,
        typo_probability: 0.05,
        message_deletion_probability: 0.02,
        quiet_hours_local_start: 120,
        quiet_hours_local_end: 360,
        require_warmup_before_commenting: true,
        min_warmup_days: 3,
        require_healthy_proxy: true,
        min_account_age_hours: 24,
        auto_pause_on_flood_wait_count: 3,
        auto_pause_on_deleted_comments_count: 5,
        quarantine_hours_on_flood_wait: 24,
        created_at: '2026-05-20T00:00:00Z',
        updated_at: '2026-05-20T00:00:00Z',
      },
      isPending: false,
      isError: false,
    }),
    useQueryClient: () => ({
      setQueryData: vi.fn(),
      invalidateQueries: vi.fn(),
    }),
  }
})

describe('SafetyPolicyPanel', () => {
  test('renders the current safety policy parameters for admins', () => {
    const html = renderToStaticMarkup(<SafetyPolicyPanel currentUserRole="admin" />)

    expect(html).toContain('Защитные пороги workspace')
    expect(html).toContain('Balanced')
    expect(html).toContain('Protection')
    expect(html).toContain('Здоровый прокси')
    expect(html).not.toContain('Behavior')
    expect(html).not.toContain('100-150 зн/мин')
  })

  test('renders read-only state for non-admin users', () => {
    const html = renderToStaticMarkup(<SafetyPolicyPanel currentUserRole="operator" />)

    expect(html).toContain('Только администратор может менять режим')
    expect(html).toContain('disabled')
  })
})
