import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, test } from 'vitest'

import { NeuroCommentingPage } from './NeuroCommentingPage'
import { neuroQueryKeys } from './hooks'
import type { NeuroCampaign } from './types'

function renderWithClient(ui: React.ReactElement, seed?: (queryClient: QueryClient) => void): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  seed?.(queryClient)
  return renderToStaticMarkup(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>)
}

function campaign(overrides: Partial<NeuroCampaign> = {}): NeuroCampaign {
  return {
    id: 'campaign-1',
    workspace_id: 'workspace-1',
    name: 'Selected campaign',
    description: null,
    status: 'draft',
    mode: 'all_posts',
    work_mode: 'manual',
    approval_mode: 'manual_required',
    send_mode: 'dry_run',
    send_strategy: 'comment',
    rotation_strategy: 'round_robin',
    language_mode: 'auto',
    prompt_template: null,
    system_prompt: null,
    negative_prompt: null,
    prompt_version: 1,
    max_comments_total: null,
    max_comments_per_hour: null,
    max_comments_per_day: null,
    delay_min_seconds: 60,
    delay_max_seconds: 300,
    rotate_after_comments: null,
    quiet_hours_start: null,
    quiet_hours_end: null,
    timezone: null,
    dry_run: true,
    auto_send_enabled: false,
    safety_enabled: true,
    started_at: null,
    stopped_at: null,
    created_at: null,
    updated_at: null,
    ...overrides,
  }
}

describe('neuro-commenting route smoke', () => {
  test('NeuroCommentingPage renders page header', () => {
    const html = renderWithClient(<NeuroCommentingPage />)
    expect(html).toContain('Нейро-комментирование')
    expect(html).toContain('Кампании')
  })

  test('NeuroCommentingPage renders empty selection prompt', () => {
    const html = renderWithClient(<NeuroCommentingPage />)
    expect(html).toContain('Выберите кампанию или создайте новую')
  })

  test('NeuroCommentingPage renders detail sections for selected campaign', () => {
    const html = renderWithClient(<NeuroCommentingPage initialSelectedCampaignId="campaign-1" />, (queryClient) => {
      queryClient.setQueryData(neuroQueryKeys.campaigns, {
        items: [campaign()],
        total: 1,
        page: 1,
        limit: 50,
      })
      queryClient.setQueryData(neuroQueryKeys.campaign('campaign-1'), campaign())
      queryClient.setQueryData(neuroQueryKeys.accounts('campaign-1'), { items: [], total: 0, page: 1, limit: 50 })
      queryClient.setQueryData(neuroQueryKeys.targets('campaign-1'), { items: [], total: 0, page: 1, limit: 50 })
      queryClient.setQueryData(neuroQueryKeys.generatedComments('campaign-1'), { items: [], total: 0, page: 1, limit: 50 })
      queryClient.setQueryData(neuroQueryKeys.events('campaign-1'), { items: [], total: 0, page: 1, limit: 50 })
    })

    expect(html).toContain('Selected campaign')
    expect(html).toContain('Аккаунты')
    expect(html).toContain('Каналы')
    expect(html).toContain('Сгенерированные комментарии')
    expect(html).toContain('События')
  })
})
