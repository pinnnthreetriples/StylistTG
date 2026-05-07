import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, test } from 'vitest'

import { AddAccountsPage } from '@/features/accounts/AddAccountsPage'
import { queryKeys } from '@/lib/queries'

function renderPage() {
  const queryClient = new QueryClient()
  queryClient.setQueryData(queryKeys.workers.diagnostics, {
    tdlib: {
      execution_plane_ready: true,
      live_enabled: true,
    },
  })

  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <AddAccountsPage
        onTestDcChange={() => undefined}
        testDcEnabled={false}
        testDcPending={false}
      />
    </QueryClientProvider>,
  )
}

describe('AddAccountsPage', () => {
  test('renders one connected account-add page without mode tabs', () => {
    const html = renderPage()

    expect(html).toContain('Введите один номер для ручной авторизации или несколько номеров для пачки.')
    expect(html).toContain('Номера')
    expect(html).toContain('Live-режим включён')
    expect(html).not.toContain('Один аккаунт')
    expect(html).not.toContain('Список номеров')
  })

  test('keeps package import on the same collapsed page', () => {
    const html = renderPage()

    expect(html).toContain('<details')
    expect(html).not.toContain('<details open')
    expect(html).toContain('Импорт пакета')
    expect(html).toContain('Введите IMPORT для подтверждения')
  })
})
