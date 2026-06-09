import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, test, vi } from 'vitest'

import type { WarmupSelectableAccount } from '../types'
import { addAllAccounts, groupSelectedAccounts, moveAccount } from './AccountSelectorModel'
import { WarmupAccountSelector } from './WarmupAccountSelector'

vi.mock('../api', () => ({
  fetchWarmupSelectableAccounts: vi.fn(),
}))

const accounts: WarmupSelectableAccount[] = [
  {
    account_id: 'acc-ca-1',
    country: 'CA',
    country_iso: 'CA',
    display_name: 'Maple Account',
    is_in_work: false,
    phase_badge: 'new',
    phone_number: '+15550101000',
    proxy_badge: 'ok',
    role: 'imported',
    tags: ['imported', 'ready'],
    username: 'maple',
    validity_badge: 'valid',
  },
  {
    account_id: 'acc-co-1',
    country: 'CO',
    country_iso: 'CO',
    display_name: 'Bogota Account',
    is_in_work: true,
    phase_badge: 'warming',
    phone_number: '+573001112233',
    proxy_badge: 'issue',
    role: 'bought',
    tags: ['bought', 'datacenter'],
    username: 'bogota',
    validity_badge: 'needs_login',
  },
]

describe('WarmupAccountSelector', () => {
  test('renders dual-list columns, filters, counters, and grouped selected accounts', () => {
    const queryClient = new QueryClient()

    const html = renderToStaticMarkup(
      <QueryClientProvider client={queryClient}>
        <WarmupAccountSelector accounts={accounts} selectedAccountIds={['acc-co-1']} onSelectionChange={vi.fn()} />
      </QueryClientProvider>,
    )

    expect(html).toContain('Аккаунты для прогрева')
    expect(html).toContain('Доступные')
    expect(html).toContain('Выбранные')
    expect(html).toContain('Все страны')
    expect(html).toContain('Maple Account')
    expect(html).toContain('Bogota Account')
    expect(html).toContain('CO · 1')
  })

  test('moves accounts with stable set-like behavior', () => {
    expect(moveAccount([], 'acc-ca-1', 'add')).toEqual(['acc-ca-1'])
    expect(moveAccount(['acc-ca-1'], 'acc-ca-1', 'add')).toEqual(['acc-ca-1'])
    expect(moveAccount(['acc-ca-1', 'acc-co-1'], 'acc-ca-1', 'remove')).toEqual(['acc-co-1'])
    expect(addAllAccounts(['acc-ca-1'], accounts)).toEqual(['acc-ca-1', 'acc-co-1'])
  })

  test('groups selected accounts by ISO country', () => {
    expect(Object.keys(groupSelectedAccounts(accounts))).toEqual(['CA', 'CO'])
  })
})
