import { PageHeader } from '@stylisttg/ui'
import { useState } from 'react'

import { ImportConfirmPanel } from '@/features/account-import/ImportConfirmPanel'
import { ImportPreviewTable } from '@/features/account-import/ImportPreviewTable'
import { ImportUploadForm } from '@/features/account-import/ImportUploadForm'
import { ImportValidationResult } from '@/features/account-import/ImportValidationResult'
import { redactImportUiError } from '@/features/account-import/importUiSecurity'
import {
  confirmAccountImportBatch,
  createAccountImportBatch,
  validateAccountImportBatch,
  type AccountImportBatch,
  type AccountImportBatchCreate,
} from '@/lib/api'

export function ImportBatchPage() {
  const [batch, setBatch] = useState<AccountImportBatch | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  async function run(action: () => Promise<AccountImportBatch>) {
    setPending(true)
    setError(null)
    try {
      setBatch(await action())
    } catch (currentError) {
      setError(currentError instanceof Error ? currentError.message : 'Действие импорта безопасно остановлено.')
    } finally {
      setPending(false)
    }
  }

  function createBatch(payload: AccountImportBatchCreate) {
    return run(() => createAccountImportBatch(payload))
  }

  function validateBatch() {
    if (!batch) return Promise.resolve()
    return run(() => validateAccountImportBatch(batch.id, {}))
  }

  function confirmBatch(confirmation: string) {
    if (!batch) return Promise.resolve()
    return run(() => confirmAccountImportBatch(batch.id, { confirmation: confirmation as 'IMPORT' }))
  }

  return (
    <div className="grid gap-4">
      <PageHeader
        eyebrow="Импорт аккаунтов"
        title="Предпросмотр пакета"
        description="Проверяет tdata, папки TDLib, файлы сессий или метаданные без автоматического live-импорта."
      />
      <ImportUploadForm disabled={pending} onCreate={createBatch} />
      <ImportConfirmPanel batch={batch} disabled={pending} onConfirm={confirmBatch} onValidate={validateBatch} />
      <ImportPreviewTable batch={batch} />
      <ImportValidationResult batch={batch} />
      {error ? (
        <div className="rounded-lg border border-amber-100 bg-amber-50 px-3 py-2 text-sm font-semibold text-amber-700">
          {redactImportUiError(error)}
        </div>
      ) : null}
    </div>
  )
}
