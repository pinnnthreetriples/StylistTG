import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, test } from 'vitest'

import { AccountsSection } from './components/AccountsSection'
import { ApprovalBadge } from './components/ApprovalBadge'
import { AttemptsSection } from './components/AttemptsSection'
import { CampaignDetailSection } from './components/CampaignDetailSection'
import { CampaignListSection } from './components/CampaignListSection'
import { CampaignStatusBadge } from './components/CampaignStatusBadge'
import { EventsSection } from './components/EventsSection'
import { GeneratedCommentsSection } from './components/GeneratedCommentsSection'
import {
  buildCampaignAccountPayload,
  buildCampaignEditorPayload,
  buildGeneratedCommentEditPayload,
  buildTargetPayload,
  parseKeywordList,
  visibleGeneratedCommentText,
} from './formPayloads'
import { neuroQueryKeys } from './hooks'
import { TargetsSection } from './components/TargetsSection'
import type { NeuroAttempt, NeuroCampaign, NeuroCampaignAccount, NeuroGeneratedComment, NeuroTarget } from './types'

function renderWithClient(ui: React.ReactElement, seed?: (queryClient: QueryClient) => void): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { refetchOnMount: false, retry: false } } })
  seed?.(queryClient)
  return renderToStaticMarkup(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>)
}

function campaign(overrides: Partial<NeuroCampaign> = {}): NeuroCampaign {
  return {
    id: 'campaign-1',
    workspace_id: 'workspace-1',
    name: 'Launch campaign',
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
    safety_preset: 'balanced',
    started_at: null,
    stopped_at: null,
    created_at: null,
    updated_at: null,
    ...overrides,
  }
}

function campaignAccount(overrides: Partial<NeuroCampaignAccount> = {}): NeuroCampaignAccount {
  return {
    id: 'campaign-account-1',
    campaign_id: 'campaign-1',
    account_id: 'account-1',
    status: 'active',
    rotation_weight: 1,
    rotation_order: 0,
    comments_sent: 0,
    comments_failed: 0,
    last_used_at: null,
    cooldown_until: null,
    last_error_code: null,
    created_at: null,
    updated_at: null,
    ...overrides,
  }
}

function target(overrides: Partial<NeuroTarget> = {}): NeuroTarget {
  return {
    id: 'target-1',
    campaign_id: 'campaign-1',
    channel_ref: '@example',
    channel_id: null,
    discussion_chat_id: null,
    title: null,
    username: null,
    status: 'active',
    source_type: 'channel',
    activity_level: null,
    keywords: [],
    exclude_keywords: [],
    last_seen_message_id: null,
    last_processed_message_id: null,
    last_commented_at: null,
    health_score: 100,
    success_count: 0,
    fail_count: 0,
    deleted_comment_count: 0,
    flood_wait_count: 0,
    created_at: null,
    updated_at: null,
    ...overrides,
  }
}

function generatedComment(overrides: Partial<NeuroGeneratedComment> = {}): NeuroGeneratedComment {
  return {
    id: 'comment-1',
    campaign_id: 'campaign-1',
    target_id: null,
    account_id: null,
    observed_post_id: null,
    generated_text: 'Generated fallback',
    edited_text: null,
    final_text: null,
    model: null,
    provider: null,
    prompt_version: 1,
    language: null,
    safety_status: 'passed',
    safety_reason: null,
    approval_status: 'pending',
    approved_by: null,
    approved_at: null,
    rejected_reason: null,
    created_at: null,
    updated_at: null,
    ...overrides,
  }
}

function attempt(overrides: Partial<NeuroAttempt> = {}): NeuroAttempt {
  return {
    id: 'attempt-1',
    campaign_id: 'campaign-1',
    generated_comment_id: 'comment-1',
    account_id: 'account-1',
    target_id: 'target-1',
    observed_post_id: 'post-1',
    status: 'created',
    send_strategy: 'comment',
    telegram_message_id: null,
    error_code: null,
    error_message: null,
    flood_wait_seconds: null,
    reserved_limit_at: null,
    sent_at: null,
    failed_at: null,
    created_at: '2026-05-18T00:00:00Z',
    updated_at: '2026-05-18T00:00:00Z',
    ...overrides,
  }
}

describe('neuro-commenting query keys', () => {
  test('campaigns key is stable', () => {
    expect(neuroQueryKeys.campaigns).toEqual(['neuro-commenting', 'campaigns'])
  })

  test('campaign key includes id', () => {
    expect(neuroQueryKeys.campaign('c-1')).toEqual(['neuro-commenting', 'campaigns', 'c-1'])
  })

  test('accounts key includes campaign id', () => {
    expect(neuroQueryKeys.accounts('c-1')).toEqual(['neuro-commenting', 'campaigns', 'c-1', 'accounts'])
  })

  test('targets key includes campaign id', () => {
    expect(neuroQueryKeys.targets('c-1')).toEqual(['neuro-commenting', 'campaigns', 'c-1', 'targets'])
  })

  test('generatedComments key falls back to all', () => {
    expect(neuroQueryKeys.generatedComments()).toEqual(['neuro-commenting', 'generated-comments', 'all'])
    expect(neuroQueryKeys.generatedComments('c-1')).toEqual(['neuro-commenting', 'generated-comments', 'c-1'])
  })

  test('attempts key falls back to all', () => {
    expect(neuroQueryKeys.attempts()).toEqual(['neuro-commenting', 'attempts', 'all'])
    expect(neuroQueryKeys.attempts('c-1')).toEqual(['neuro-commenting', 'attempts', 'c-1'])
  })

  test('events key falls back to all', () => {
    expect(neuroQueryKeys.events()).toEqual(['neuro-commenting', 'events', 'all'])
    expect(neuroQueryKeys.events('c-1')).toEqual(['neuro-commenting', 'events', 'c-1'])
  })
})

describe('neuro-commenting section components', () => {
  test('CampaignListSection renders campaigns from query data', () => {
    const html = renderWithClient(<CampaignListSection selectedId={null} onSelect={() => undefined} />, (queryClient) => {
      queryClient.setQueryData(neuroQueryKeys.campaigns, {
        items: [campaign({ name: 'Seeded campaign' })],
        total: 1,
        page: 1,
        limit: 50,
      })
    })

    expect(html).toContain('Seeded campaign')
  })

  test('AccountsSection renders loading skeleton', () => {
    const html = renderWithClient(<AccountsSection campaignId="c-1" />)
    expect(html).toContain('data-slot="skeleton"')
  })

  test('AccountsSection renders add form', () => {
    const html = renderWithClient(<AccountsSection campaignId="campaign-1" />, (queryClient) => {
      queryClient.setQueryData(neuroQueryKeys.accounts('campaign-1'), {
        items: [campaignAccount()],
        total: 1,
        page: 1,
        limit: 50,
      })
    })

    expect(html).toContain('account_id')
    expect(html).toContain('Добавить')
    expect(html).toContain('Удалить')
  })

  test('CampaignDetailSection renders observe campaign button', () => {
    const html = renderWithClient(<CampaignDetailSection campaignId="campaign-1" />, (queryClient) => {
      queryClient.setQueryData(neuroQueryKeys.campaign('campaign-1'), campaign())
    })

    expect(html).toContain('Observe campaign now')
  })

  test('TargetsSection renders loading skeleton', () => {
    const html = renderWithClient(<TargetsSection campaignId="c-1" />)
    expect(html).toContain('data-slot="skeleton"')
  })

  test('TargetsSection renders add form', () => {
    const html = renderWithClient(<TargetsSection campaignId="campaign-1" />, (queryClient) => {
      queryClient.setQueryData(neuroQueryKeys.targets('campaign-1'), {
        items: [target()],
        total: 1,
        page: 1,
        limit: 50,
      })
    })

    expect(html).toContain('channel_ref')
    expect(html).toContain('Добавить канал')
    expect(html).toContain('Refresh metadata')
    expect(html).toContain('Observe target')
    expect(html).toContain('Удалить')
  })

  test('EventsSection renders loading skeleton', () => {
    const html = renderWithClient(<EventsSection campaignId="c-1" />)
    expect(html).toContain('data-slot="skeleton"')
  })

  test('GeneratedCommentsSection displays generated text fallback and pending actions', () => {
    const html = renderWithClient(<GeneratedCommentsSection campaignId="campaign-1" />, (queryClient) => {
      queryClient.setQueryData(neuroQueryKeys.generatedComments('campaign-1'), {
        items: [generatedComment()],
        total: 1,
        page: 1,
        limit: 50,
      })
    })

    expect(html).toContain('Generated fallback')
    expect(html).toContain('Редактировать')
    expect(html).toContain('Одобрить')
    expect(html).toContain('Отклонить')
  })

  test('GeneratedCommentsSection renders approve/reject controls for edited comments', () => {
    const html = renderWithClient(<GeneratedCommentsSection campaignId="campaign-1" />, (queryClient) => {
      queryClient.setQueryData(neuroQueryKeys.generatedComments('campaign-1'), {
        items: [
          generatedComment({
            approval_status: 'edited',
            edited_text: 'Edited text',
            final_text: 'Edited text',
          }),
        ],
        total: 1,
        page: 1,
        limit: 50,
      })
    })

    expect(html).toContain('Edited text')
    expect(html).toContain('Редактировать')
    expect(html).toContain('Одобрить')
    expect(html).toContain('Отклонить')
  })

  test('GeneratedCommentsSection renders manual send for approved comments', () => {
    const html = renderWithClient(<GeneratedCommentsSection campaignId="campaign-1" />, (queryClient) => {
      queryClient.setQueryData(neuroQueryKeys.generatedComments('campaign-1'), {
        items: [generatedComment({ approval_status: 'approved', final_text: 'Approved text' })],
        total: 1,
        page: 1,
        limit: 50,
      })
    })

    expect(html).toContain('Send manually')
  })

  test('AttemptsSection renders attempt status', () => {
    const html = renderWithClient(<AttemptsSection campaignId="campaign-1" />, (queryClient) => {
      queryClient.setQueryData(neuroQueryKeys.attempts('campaign-1'), {
        items: [attempt({ status: 'sent', telegram_message_id: 'telegram-1' })],
        total: 1,
        page: 1,
        limit: 50,
      })
    })

    expect(html).toContain('Attempts')
    expect(html).toContain('sent')
    expect(html).toContain('telegram-1')
  })
})

describe('neuro-commenting form payload helpers', () => {
  test('buildCampaignAccountPayload trims account id and parses rotation fields', () => {
    expect(buildCampaignAccountPayload({ accountId: ' account-1 ', rotationWeight: '2', rotationOrder: '3' })).toEqual({
      account_id: 'account-1',
      rotation_weight: 2,
      rotation_order: 3,
    })
  })

  test('parseKeywordList trims comma-separated keywords', () => {
    expect(parseKeywordList('ai, marketing, tg')).toEqual(['ai', 'marketing', 'tg'])
    expect(parseKeywordList(' ai, ,tg ')).toEqual(['ai', 'tg'])
  })

  test('buildTargetPayload trims channel and parses keyword fields', () => {
    expect(
      buildTargetPayload({
        channelRef: ' @channel ',
        title: ' Product ',
        keywords: 'ai, marketing, tg',
        excludeKeywords: 'spam, ads',
      }),
    ).toEqual({
      channel_ref: '@channel',
      title: 'Product',
      source_type: 'channel',
      keywords: ['ai', 'marketing', 'tg'],
      exclude_keywords: ['spam', 'ads'],
    })
  })

  test('visibleGeneratedCommentText falls back from final to edited to generated text', () => {
    expect(visibleGeneratedCommentText(generatedComment({ final_text: 'Final' }))).toBe('Final')
    expect(visibleGeneratedCommentText(generatedComment({ edited_text: 'Edited' }))).toBe('Edited')
    expect(visibleGeneratedCommentText(generatedComment())).toBe('Generated fallback')
  })

  test('buildGeneratedCommentEditPayload rejects empty text', () => {
    expect(buildGeneratedCommentEditPayload(' Updated ')).toEqual({ edited_text: 'Updated' })
    expect(() => buildGeneratedCommentEditPayload('   ')).toThrow('edited_text required')
  })

  test('buildCampaignEditorPayload rejects delay max below backend minimum', () => {
    expect(() =>
      buildCampaignEditorPayload({
        promptTemplate: '',
        languageMode: 'auto',
        mode: 'all_posts',
        workMode: 'manual',
        approvalMode: 'manual_required',
        maxCommentsPerHour: '',
        maxCommentsPerDay: '',
        delayMinSeconds: '0',
        delayMaxSeconds: '10',
        safetyEnabled: true,
      }),
    ).toThrow('delay_max_seconds invalid')
  })
})

describe('neuro-commenting UI helpers', () => {
  test('CampaignStatusBadge renders known statuses', () => {
    expect(renderToStaticMarkup(<CampaignStatusBadge status="draft" />)).toContain('draft')
    expect(renderToStaticMarkup(<CampaignStatusBadge status="running" />)).toContain('running')
    expect(renderToStaticMarkup(<CampaignStatusBadge status="paused" />)).toContain('paused')
    expect(renderToStaticMarkup(<CampaignStatusBadge status="stopped" />)).toContain('stopped')
  })

  test('CampaignStatusBadge falls back to neutral for unknown status', () => {
    const html = renderToStaticMarkup(<CampaignStatusBadge status="unknown_value" />)
    expect(html).toContain('unknown_value')
  })

  test('ApprovalBadge renders approval statuses', () => {
    expect(renderToStaticMarkup(<ApprovalBadge status="pending" />)).toContain('pending')
    expect(renderToStaticMarkup(<ApprovalBadge status="approved" />)).toContain('approved')
    expect(renderToStaticMarkup(<ApprovalBadge status="rejected" />)).toContain('rejected')
    expect(renderToStaticMarkup(<ApprovalBadge status="edited" />)).toContain('edited')
  })

  test('ApprovalBadge falls back to neutral for unknown status', () => {
    const html = renderToStaticMarkup(<ApprovalBadge status="custom" />)
    expect(html).toContain('custom')
  })
})
