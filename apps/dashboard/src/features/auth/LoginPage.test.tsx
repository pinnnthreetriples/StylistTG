import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, test, vi } from 'vitest'

import { LoginPageView } from '@/features/auth/LoginPage'

describe('LoginPageView', () => {
  test('renders Russian email auth labels without tokens', () => {
    const html = renderToStaticMarkup(
      <LoginPageView
        error="Не удалось войти. Проверьте email и пароль."
        mode="login"
        onModeChange={vi.fn()}
        onSubmit={vi.fn()}
        pending={false}
      />,
    )

    expect(html).toContain('Войти в StylistTG')
    expect(html).toContain('Email')
    expect(html).toContain('Пароль')
    expect(html).toContain('Войти')
    expect(html).toContain('Создать аккаунт')
    expect(html).not.toContain('access_token')
    expect(html).not.toContain('jwt-')
  })
})
