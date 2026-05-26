import { useForm } from '@tanstack/react-form'
import { Button, SectionCard } from '@stylisttg/ui'
import { useState } from 'react'

import {
  buildBatchImportPreview,
  createDefaultBatchImportDraft,
  validateBatchImportDraft,
  type BatchImportSourceType,
} from '@/features/batch-import/batchImportModel'

export function BatchImportForm() {
  const [preview, setPreview] = useState<ReturnType<typeof buildBatchImportPreview> | null>(null)
  const form = useForm({
    defaultValues: createDefaultBatchImportDraft(),
    onSubmit: ({ value }) => {
      const errors = validateBatchImportDraft(value)
      if (errors.length === 0) {
        setPreview(buildBatchImportPreview(value))
      }
    },
  })

  return (
    <SectionCard title="Batch import preview">
      <form
        className="grid gap-4"
        onSubmit={(event) => {
          event.preventDefault()
          event.stopPropagation()
          void form.handleSubmit()
        }}
      >
        <form.Field name="label" validators={{ onChange: ({ value }) => (value.length > 80 ? 'Max 80 characters.' : undefined) }}>
          {(field) => (
            <label className="grid gap-1.5 text-sm font-semibold text-foreground">
              Batch label
              <input
                className="rounded-lg border border-border px-3 py-2 text-sm font-normal"
                onBlur={field.handleBlur}
                onChange={(event) => field.handleChange(event.target.value)}
                placeholder="May staging dry run"
                value={field.state.value}
              />
            </label>
          )}
        </form.Field>

        <form.Field name="sourceType" validators={{ onChange: ({ value }) => (!value ? 'Source type is required.' : undefined) }}>
          {(field) => (
            <label className="grid gap-1.5 text-sm font-semibold text-foreground">
              Source type
              <select
                className="rounded-lg border border-border px-3 py-2 text-sm font-normal"
                onBlur={field.handleBlur}
                onChange={(event) => field.handleChange(event.target.value as BatchImportSourceType)}
                value={field.state.value}
              >
                <option value="">Choose source</option>
                <option value="tdata">tdata</option>
                <option value="session">session</option>
                <option value="json">json</option>
                <option value="manual-placeholder">manual-placeholder</option>
              </select>
            </label>
          )}
        </form.Field>

        <form.Field name="notes">
          {(field) => (
            <label className="grid gap-1.5 text-sm font-semibold text-foreground">
              Notes
              <textarea
                className="min-h-24 rounded-lg border border-border px-3 py-2 text-sm font-normal"
                onBlur={field.handleBlur}
                onChange={(event) => field.handleChange(event.target.value)}
                value={field.state.value}
              />
            </label>
          )}
        </form.Field>

        <form.Field name="dryRun">
          {(field) => (
            <label className="flex items-center gap-2 text-sm font-semibold text-foreground">
              <input
                checked={field.state.value}
                onBlur={field.handleBlur}
                onChange={(event) => field.handleChange(event.target.checked)}
                type="checkbox"
              />
              Dry run only
            </label>
          )}
        </form.Field>

        <Button type="submit">Preview import payload</Button>
      </form>

      {preview ? (
        <pre className="mt-4 overflow-auto rounded-lg bg-foreground p-4 text-xs text-primary-foreground">
          {JSON.stringify(preview, null, 2)}
        </pre>
      ) : null}
    </SectionCard>
  )
}
