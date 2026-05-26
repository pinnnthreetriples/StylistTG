import { useQuery } from '@tanstack/react-query'

import { ImportBatchPage } from '@/features/account-import/ImportBatchPage'
import { BulkAuthScreen } from '@/components/auth/BulkAuthScreen'
import { getLiveStatus } from '@/lib/liveStatus'
import { frontendDiagnosticsQueryOptions, workerDiagnosticsQueryOptions } from '@/lib/queries'

export function AddAccountsPage({
  testDcEnabled,
  testDcPending,
  onTestDcChange,
}: {
  testDcEnabled: boolean
  testDcPending: boolean
  onTestDcChange: (enabled: boolean) => void
}) {
  const diagnosticsQuery = useQuery(frontendDiagnosticsQueryOptions())
  const workerDiagnosticsQuery = useQuery(workerDiagnosticsQueryOptions())
  const liveStatus = getLiveStatus(diagnosticsQuery.data, workerDiagnosticsQuery.data)

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6">
      <div className="mb-6 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="font-sans text-2xl font-bold tracking-tight text-foreground">
            Добавление аккаунтов
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Введите один или несколько номеров для запуска авторизации.
          </p>
        </div>
      </div>

      <div className="grid gap-4">
        <BulkAuthScreen
          liveStatus={liveStatus}
          onTestDcChange={onTestDcChange}
          testDcEnabled={testDcEnabled}
          testDcPending={testDcPending}
        />
        <details className="rounded-xl border border-border bg-card shadow-sm">
          <summary className="cursor-pointer list-none px-4 py-3 text-sm font-semibold text-foreground">
            Импорт пакета
            <span className="ml-2 font-normal text-muted-foreground">предпросмотр и ручное подтверждение</span>
          </summary>
          <div className="border-t border-border p-4">
            <ImportBatchPage compact />
          </div>
        </details>
      </div>
    </div>
  )
}
