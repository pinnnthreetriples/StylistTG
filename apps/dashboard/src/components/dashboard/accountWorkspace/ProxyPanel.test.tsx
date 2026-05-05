import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, test } from 'vitest'

import { ProxyPanel } from './WorkspacePanels'

describe('ProxyPanel', () => {
  test('renders Russian safety copy without exposing proxy password', () => {
    const html = renderToStaticMarkup(
      <ProxyPanel
        isChecking={false}
        isDeleting={false}
        isSaving={false}
        onCheck={() => undefined}
        onDelete={() => undefined}
        onSave={() => undefined}
        proxy={{
          account_id: 'acc_1',
          created_at: '2026-05-01T00:00:00Z',
          has_password: true,
          host: 'proxy.example.com',
          last_checked_at: null,
          last_check_scope: null,
          last_error_code: null,
          last_error_message: null,
          port: 1080,
          proxy_type: 'socks5',
          status: 'configured',
          tdlib_last_error_code: null,
          tdlib_last_error_message: null,
          tdlib_verified_at: null,
          updated_at: '2026-05-01T00:00:00Z',
          username: 'operator',
        }}
      />,
    )

    expect(html).toContain('Оставьте пустым, чтобы не менять пароль')
    expect(html).toContain('Проверить прокси')
    expect(html).not.toContain('hunter2')
    expect(html).not.toContain('proxy_password')
  })
})
