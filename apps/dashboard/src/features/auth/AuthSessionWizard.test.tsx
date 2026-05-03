import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, test } from 'vitest'

import { AuthSessionWizard } from '@/features/auth/AuthSessionWizard'
import { redactAuthUiError } from '@/features/auth/authUiSecurity'
import { SubmitCodeForm } from '@/features/auth/SubmitCodeForm'
import { SubmitPasswordForm } from '@/features/auth/SubmitPasswordForm'

describe('AuthSessionWizard', () => {
  test('renders TDLib live auth safety copy', () => {
    const html = renderToStaticMarkup(<AuthSessionWizard />)

    expect(html).toContain('TDLib auth foundation')
    expect(html).toContain('live runtime disabled')
    expect(html).toContain('Codes and passwords are never stored')
  })

  test('code and password forms avoid persisted default values', () => {
    const codeHtml = renderToStaticMarkup(<SubmitCodeForm onSubmitCode={async () => undefined} />)
    const passwordHtml = renderToStaticMarkup(<SubmitPasswordForm onSubmitPassword={async () => undefined} />)

    expect(codeHtml).toContain('autoComplete="one-time-code"')
    expect(codeHtml).not.toContain('12345')
    expect(passwordHtml).toContain('type="password"')
    expect(passwordHtml).not.toContain('hunter2')
  })

  test('redacts secret-looking error fragments', () => {
    expect(redactAuthUiError('code=12345 password=hunter2 token=abc')).toBe(
      'code=[redacted] password=[redacted] token=[redacted]',
    )
  })
})
