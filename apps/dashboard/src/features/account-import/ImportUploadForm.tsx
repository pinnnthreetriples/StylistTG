import { Button, SectionCard } from '@stylisttg/ui'
import { useState } from 'react'

import type { AccountImportBatchCreate } from '@/lib/api'

export function ImportUploadForm({
  disabled,
  onCreate,
}: {
  disabled?: boolean
  onCreate: (payload: AccountImportBatchCreate) => Promise<void>
}) {
  const [label, setLabel] = useState('')
  const [sourceType, setSourceType] = useState<AccountImportBatchCreate['source_type']>('json-metadata')

  return (
    <SectionCard
      title="Create import batch"
      description="Upload/import validation is dry-run first. Unsupported session formats require manual reauthorization."
    >
      <form
        className="grid gap-3 md:grid-cols-[1fr_220px_auto]"
        onSubmit={(event) => {
          event.preventDefault()
          void onCreate({ dry_run: true, label: label.trim() || undefined, source_type: sourceType })
        }}
      >
        <label className="grid gap-1 text-sm font-medium text-gray-700">
          Batch label
          <input
            className="h-10 rounded-md border border-gray-200 px-3 text-sm"
            disabled={disabled}
            onChange={(event) => setLabel(event.target.value)}
            placeholder="May import"
            value={label}
          />
        </label>
        <label className="grid gap-1 text-sm font-medium text-gray-700">
          Source type
          <select
            className="h-10 rounded-md border border-gray-200 px-3 text-sm"
            disabled={disabled}
            onChange={(event) => setSourceType(event.target.value as AccountImportBatchCreate['source_type'])}
            value={sourceType}
          >
            <option value="json-metadata">json-metadata</option>
            <option value="tdlib-directory">tdlib-directory</option>
            <option value="tdata">tdata</option>
            <option value="session-file">session-file</option>
          </select>
        </label>
        <Button className="self-end" disabled={disabled} type="submit">
          Create dry-run batch
        </Button>
      </form>
    </SectionCard>
  )
}
