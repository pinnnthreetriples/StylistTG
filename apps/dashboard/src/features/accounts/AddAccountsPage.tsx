import { useState } from 'react'

import { AnimatedTabs } from '@/components/ui/AnimatedTabs'
import { AuthSessionWizard } from '@/features/auth/AuthSessionWizard'
import { ImportBatchPage } from '@/features/account-import/ImportBatchPage'
import { BulkAuthScreen } from '@/components/auth/BulkAuthScreen'

export function AddAccountsPage({
  testDcEnabled,
  testDcPending,
  onTestDcChange,
  onBack,
}: {
  testDcEnabled: boolean
  testDcPending: boolean
  onTestDcChange: (enabled: boolean) => void
  onBack: () => void
}) {
  const [activeTab, setActiveTab] = useState('single')

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6">
      <div className="mb-6 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="font-display text-2xl font-bold tracking-tight text-gray-900">
            Добавление аккаунтов
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            Выберите удобный способ добавления аккаунтов в систему.
          </p>
        </div>
      </div>

      <AnimatedTabs
        value={activeTab}
        onValueChange={setActiveTab}
        tabs={[
          {
            value: 'single',
            label: 'Один аккаунт',
            content: (
              <div className="py-4">
                <AuthSessionWizard />
              </div>
            ),
          },
          {
            value: 'list',
            label: 'Список номеров',
            content: (
              <div className="py-4">
                <BulkAuthScreen
                  onBack={onBack}
                  onTestDcChange={onTestDcChange}
                  testDcEnabled={testDcEnabled}
                  testDcPending={testDcPending}
                />
              </div>
            ),
          },
          {
            value: 'import',
            label: 'Импорт пакета',
            content: (
              <div className="py-4">
                <ImportBatchPage />
              </div>
            ),
          },
        ]}
      />
    </div>
  )
}
