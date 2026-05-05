import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, test } from 'vitest'

import { AccountRiskTab } from './AccountRiskTab'

describe('AccountRiskTab', () => {
  test('renders primary risk state without raw backend enums', () => {
    const html = renderToStaticMarkup(
      <AccountRiskTab
        accountState="execution_usable"
        proxyStatus="failed"
        risk={{
          account_id: 'acc_1',
          computed_at: '2026-05-04T00:00:00Z',
          level: 'high',
          recommended_action: 'Перед изменением профиля проверьте аккаунт.',
          reasons: [{ code: 'reauth_required', message: 'reauth_required', severity: 'critical' }],
          score: 72,
        }}
        runtimeHealth="ready"
      />,
    )

    expect(html).toContain('Высокий риск')
    expect(html).toContain('Нужна повторная авторизация')
    expect(html).toContain('Готов к задачам')
    expect(html).toContain('Готов')
    expect(html).toContain('Ошибка подключения')
    expect(html).not.toContain('execution_usable')
    expect(html).not.toContain('reauth_required')
    expect(html).not.toContain('tdlib_failed')
  })
})
