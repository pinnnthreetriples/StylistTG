import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, test } from 'vitest'

import { NeuroCommentingPage } from './NeuroCommentingPage'

function renderWithClient(ui: React.ReactElement): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return renderToStaticMarkup(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>)
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
})
