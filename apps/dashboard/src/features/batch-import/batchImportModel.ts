export type BatchImportSourceType = '' | 'tdata' | 'session' | 'json' | 'manual-placeholder'

export type BatchImportDraft = {
  label: string
  sourceType: BatchImportSourceType
  notes: string
  dryRun: boolean
}

export function createDefaultBatchImportDraft(): BatchImportDraft {
  return {
    label: '',
    sourceType: '',
    notes: '',
    dryRun: true,
  }
}

export function validateBatchImportDraft(value: BatchImportDraft): string[] {
  const errors: string[] = []
  if (!value.sourceType) errors.push('Source type is required.')
  if (value.label.length > 80) errors.push('Batch label must be 80 characters or fewer.')
  if (!value.dryRun) errors.push('Dry run must stay enabled in this foundation flow.')
  return errors
}

export function buildBatchImportPreview(value: BatchImportDraft) {
  return {
    label: value.label.trim() || 'Untitled import batch',
    source_type: value.sourceType,
    notes: value.notes.trim(),
    dry_run: value.dryRun,
    execution: 'preview_only',
  }
}
