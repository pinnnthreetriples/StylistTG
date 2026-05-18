import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, test } from 'vitest'

import { AccountsSection } from './components/AccountsSection'
import { ApprovalBadge } from './components/ApprovalBadge'
import { CampaignStatusBadge } from './components/CampaignStatusBadge'
import { EventsSection } from './components/EventsSection'
import { TargetsSection } from './components/TargetsSection'
import { neuroQueryKeys } from './hooks'

function renderWithClient(ui: React.ReactElement): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return renderToStaticMarkup(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>)
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

  test('events key falls back to all', () => {
    expect(neuroQueryKeys.events()).toEqual(['neuro-commenting', 'events', 'all'])
    expect(neuroQueryKeys.events('c-1')).toEqual(['neuro-commenting', 'events', 'c-1'])
  })
})

describe('neuro-commenting section components', () => {
  test('AccountsSection renders loading skeleton', () => {
    const html = renderWithClient(<AccountsSection campaignId="c-1" />)
    expect(html).toContain('skeleton')
  })

  test('TargetsSection renders loading skeleton', () => {
    const html = renderWithClient(<TargetsSection campaignId="c-1" />)
    expect(html).toContain('skeleton')
  })

  test('EventsSection renders loading skeleton', () => {
    const html = renderWithClient(<EventsSection campaignId="c-1" />)
    expect(html).toContain('skeleton')
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
