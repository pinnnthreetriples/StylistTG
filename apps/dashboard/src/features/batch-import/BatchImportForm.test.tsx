import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, test } from 'vitest'

import { BatchImportForm } from '@/features/batch-import/BatchImportForm'
import {
  buildBatchImportPreview,
  createDefaultBatchImportDraft,
  validateBatchImportDraft,
} from '@/features/batch-import/batchImportModel'

describe('BatchImportForm', () => {
  test('defaults to dry-run mode', () => {
    expect(createDefaultBatchImportDraft().dryRun).toBe(true)
  })

  test('validates required source type and dry-run guard', () => {
    expect(validateBatchImportDraft({ label: '', sourceType: '', notes: '', dryRun: true })).toContain(
      'Source type is required.',
    )
    expect(validateBatchImportDraft({ label: '', sourceType: 'json', notes: '', dryRun: false })).toContain(
      'Dry run must stay enabled in this foundation flow.',
    )
  })

  test('builds preview payload without execution intent', () => {
    expect(buildBatchImportPreview({ label: 'May', sourceType: 'json', notes: '', dryRun: true })).toMatchObject({
      execution: 'preview_only',
      dry_run: true,
    })
  })

  test('renders the preview form', () => {
    const html = renderToStaticMarkup(<BatchImportForm />)

    expect(html).toContain('Batch import preview')
    expect(html).toContain('Dry run only')
  })
})
