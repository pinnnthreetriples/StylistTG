import { Button, SectionCard } from '@stylisttg/ui'
import { useState } from 'react'

import type { AccountImportBatchCreate } from '@/lib/api'
import { labelImportSourceType } from '@/lib/uiLabels'

const importSourceOptions: Array<{ label: string; value: AccountImportBatchCreate['source_type'] }> = [
  { label: labelImportSourceType('json-metadata'), value: 'json-metadata' },
  { label: labelImportSourceType('tdlib-directory'), value: 'tdlib-directory' },
  { label: labelImportSourceType('tdata'), value: 'tdata' },
  { label: labelImportSourceType('session-file'), value: 'session-file' },
]

export function ImportUploadForm({
  disabled,
  onCreate,
}: {
  disabled?: boolean
  onCreate: (payload: AccountImportBatchCreate) => Promise<void>
}) {
  const [label, setLabel] = useState('')
  const [sourceTypeLabel, setSourceTypeLabel] = useState(importSourceOptions[0].label)
  const sourceType = importSourceOptions.find((option) => option.label === sourceTypeLabel)?.value ?? 'json-metadata'

  return (
    <SectionCard
      title="Проверить пакет"
      description="Сначала выполняется предпросмотр. Неподдерживаемые форматы сессий требуют ручного повторного входа."
    >
      <form
        className="grid gap-3 md:grid-cols-[1fr_220px_auto]"
        onSubmit={(event) => {
          event.preventDefault()
          void onCreate({ dry_run: true, label: label.trim() || undefined, source_type: sourceType })
        }}
      >
        <label className="grid gap-1 text-sm font-medium text-gray-700">
          Название пакета
          <input
            className="h-10 rounded-md border border-gray-200 px-3 text-sm"
            disabled={disabled}
            onChange={(event) => setLabel(event.target.value)}
            placeholder="Например: майский импорт"
            value={label}
          />
        </label>
        <label className="grid gap-1 text-sm font-medium text-gray-700">
          Тип источника
          <select
            className="h-10 rounded-md border border-gray-200 px-3 text-sm"
            disabled={disabled}
            onChange={(event) => setSourceTypeLabel(event.target.value)}
            value={sourceTypeLabel}
          >
            {importSourceOptions.map((option) => (
              <option key={option.value} value={option.label}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <Button className="self-end" disabled={disabled} type="submit" variant="secondary">
          Создать предпросмотр
        </Button>
      </form>
    </SectionCard>
  )
}
