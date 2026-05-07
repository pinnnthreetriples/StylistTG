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
          <h1 className="font-display text-2xl font-bold tracking-tight text-gray-900">
            Добавление аккаунтов
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            Введите один номер для ручной авторизации или несколько номеров для пачки.
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
        <details className="rounded-xl border border-gray-200/70 bg-white shadow-soft">
          <summary className="cursor-pointer list-none px-4 py-3 text-sm font-semibold text-navy-900">
            Импорт пакета
            <span className="ml-2 font-normal text-gray-400">предпросмотр и ручное подтверждение</span>
          </summary>
          <div className="border-t border-gray-100 p-4">
            <ImportBatchPage compact />
          </div>
        </details>
      </div>
    </div>
  )
}
