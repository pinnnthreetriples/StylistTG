import { Button, SectionCard, StatusPill } from '@stylisttg/ui'
import { useState } from 'react'

import type { AccountImportBatch } from '@/lib/api'

export function ImportConfirmPanel({
  batch,
  disabled,
  onConfirm,
  onValidate,
}: {
  batch: AccountImportBatch | null
  disabled?: boolean
  onConfirm: (confirmation: string) => Promise<void>
  onValidate: () => Promise<void>
}) {
  const [confirmation, setConfirmation] = useState('')
  const canConfirm = batch?.status === 'preview_ready' && confirmation === 'IMPORT'

  return (
    <SectionCard title="Validation and confirmation" description="Confirmation remains explicit; unsupported sessions are not attached automatically.">
      <div className="flex flex-wrap items-center gap-2">
        <StatusPill tone={batch?.dry_run === false ? 'amber' : 'green'}>{batch?.dry_run === false ? 'execution requested' : 'dry-run'}</StatusPill>
        <StatusPill tone="muted">{batch?.status ?? 'no batch'}</StatusPill>
        <StatusPill tone="muted">items: {batch?.item_count ?? 0}</StatusPill>
      </div>
      <div className="mt-4 flex flex-col gap-3 sm:flex-row">
        <Button disabled={disabled || !batch} onClick={() => void onValidate()} variant="secondary">
          Validate dry-run
        </Button>
        <input
          className="h-10 flex-1 rounded-md border border-gray-200 px-3 text-sm"
          disabled={disabled || !batch}
          onChange={(event) => setConfirmation(event.target.value)}
          placeholder="Type IMPORT to confirm"
          value={confirmation}
        />
        <Button disabled={disabled || !canConfirm} onClick={() => void onConfirm(confirmation)}>
          Confirm import
        </Button>
      </div>
    </SectionCard>
  )
}
