import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, describe, expect, test, vi } from 'vitest'

import { AddAccountsPage } from '@/features/accounts/AddAccountsPage'
import { canConfirmOnboardingBatch } from '@/features/accounts/accountOnboardingWizard'

const DRAFT_KEY = 'stylisttg.account_onboarding_draft'

afterEach(() => {
  vi.unstubAllGlobals()
})

function renderPage() {
  const queryClient = new QueryClient()
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <AddAccountsPage onTestDcChange={() => undefined} testDcEnabled={false} testDcPending={false} />
    </QueryClientProvider>,
  )
}

describe('AddAccountsPage', () => {
  test('renders canonical account onboarding wizard as first screen', () => {
    const html = renderPage()

    expect(html).toContain('Добавление аккаунтов')
    expect(html).toContain('Номера')
    expect(html).toContain('TDLib')
    expect(html).toContain('tdata')
    expect(html).toContain('Session')
    expect(html).toContain('Требуется ручная авторизация')
    expect(html).toContain('0 номеров')
    expect(html).toContain('Метка')
    expect(html).toContain('Предпросмотр')
    expect(html).toContain('Очистить черновик')
    expect(html).not.toContain('<details')
    expect(html).not.toContain('BulkAuthScreen')
  })

  test('reads saved draft raw input on first render', () => {
    vi.stubGlobal('window', {
      localStorage: {
        getItem: (key: string) =>
          key === DRAFT_KEY
            ? JSON.stringify({
                sourceType: 'phone_bulk',
                label: 'Saved',
                rawInput: '+15550102000 Saved label',
                jsonInput: '{}',
              })
            : null,
        removeItem: () => undefined,
        setItem: () => undefined,
      },
    })

    const html = renderPage()

    expect(html).toContain('+15550102000 Saved label')
    expect(html).toContain('1 номеров')
  })

  test('blocks confirm until explicit consent is checked', () => {
    expect(canConfirmOnboardingBatch('preview_ready', false, false)).toBe(false)
    expect(canConfirmOnboardingBatch('preview_ready', true, true)).toBe(false)
    expect(canConfirmOnboardingBatch('created', true, false)).toBe(false)
    expect(canConfirmOnboardingBatch('preview_ready', true, false)).toBe(true)
  })
})
