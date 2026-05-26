import { Button, SectionCard, StatusPill } from '@stylisttg/ui'
import { useState } from 'react'

import type { AccountImportBatch } from '@/lib/api'
import { labelImportStatus } from '@/lib/uiLabels'

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
    <SectionCard title="Проверка и подтверждение" description="Подтверждение всегда явное. Неподдерживаемые сессии не подключаются автоматически.">
      <div className="flex flex-wrap items-center gap-2">
        <StatusPill tone={batch?.dry_run === false ? 'amber' : 'green'}>{batch?.dry_run === false ? 'Запрошено выполнение' : 'Предпросмотр'}</StatusPill>
        <StatusPill tone="muted">{labelImportStatus(batch?.status)}</StatusPill>
        <StatusPill tone="muted">Строк: {batch?.item_count ?? 0}</StatusPill>
      </div>
      <div className="mt-4 flex flex-col gap-3 sm:flex-row">
        <Button disabled={disabled || !batch} onClick={() => void onValidate()} variant="secondary">
          Проверить
        </Button>
        <input
          className="h-10 flex-1 rounded-md border border-border px-3 text-sm"
          disabled={disabled || !batch}
          onChange={(event) => setConfirmation(event.target.value)}
          placeholder="Введите IMPORT для подтверждения"
          value={confirmation}
        />
        <Button disabled={disabled || !canConfirm} onClick={() => void onConfirm(confirmation)}>
          Подтвердить импорт
        </Button>
      </div>
    </SectionCard>
  )
}
