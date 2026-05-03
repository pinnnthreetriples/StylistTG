import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, test } from 'vitest'

import { ImportConfirmPanel } from '@/features/account-import/ImportConfirmPanel'
import { ImportBatchPage } from '@/features/account-import/ImportBatchPage'
import { redactImportUiError } from '@/features/account-import/importUiSecurity'

describe('ImportBatchPage', () => {
  test('renders dry-run import foundation', () => {
    const html = renderToStaticMarkup(<ImportBatchPage />)

    expect(html).toContain('Account import foundation')
    expect(html).toContain('dry-run')
    expect(html).toContain('preview-first')
    expect(html).toContain('Type IMPORT to confirm')
  })

  test('confirmation is disabled without explicit IMPORT text', () => {
    const html = renderToStaticMarkup(
      <ImportConfirmPanel batch={null} onConfirm={async () => undefined} onValidate={async () => undefined} />,
    )

    expect(html).toContain('Type IMPORT to confirm')
    expect(html).toContain('disabled=""')
  })

  test('redacts secret-looking import errors', () => {
    expect(redactImportUiError('api_hash=abc session=/tmp/path password=hunter2')).toBe(
      'api_hash=[redacted] session=[redacted] password=[redacted]',
    )
  })
})
