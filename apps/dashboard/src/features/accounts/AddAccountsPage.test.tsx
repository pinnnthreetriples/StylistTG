import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, test } from 'vitest'

import { AddAccountsPage } from '@/features/accounts/AddAccountsPage'

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
    expect(html).toContain('Полная поддержка')
    expect(html).toContain('0 номеров')
    expect(html).not.toContain('<details')
    expect(html).not.toContain('BulkAuthScreen')
  })
})
