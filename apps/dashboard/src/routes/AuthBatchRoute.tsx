import { useNavigate } from '@tanstack/react-router'
import { useCallback, useEffect, useState } from 'react'

import { BulkAuthScreen } from '@/components/auth/BulkAuthScreen'
import { BatchImportForm } from '@/features/batch-import/BatchImportForm'
import { fetchAuthRuntimeMode, updateAuthRuntimeMode } from '@/lib/auth'
import { appRoutes } from '@/lib/routes'

export function AuthBatchRoute() {
  const navigate = useNavigate()
  const [testDcEnabled, setTestDcEnabled] = useState(false)
  const [testDcPending, setTestDcPending] = useState(false)

  useEffect(() => {
    let active = true
    void fetchAuthRuntimeMode()
      .then((mode) => {
        if (active) setTestDcEnabled(mode.tdlib_use_test_dc)
      })
      .catch(() => {
        if (active) setTestDcEnabled(false)
      })
    return () => {
      active = false
    }
  }, [])

  const handleTestDcChange = useCallback(async (enabled: boolean) => {
    setTestDcPending(true)
    try {
      const mode = await updateAuthRuntimeMode(enabled)
      setTestDcEnabled(mode.tdlib_use_test_dc)
    } catch {
      // Keep the previous mode visible; batch form actions report their own errors.
    } finally {
      setTestDcPending(false)
    }
  }, [])

  return (
    <div className="mx-auto grid max-w-5xl gap-5 px-5 py-6">
      <BatchImportForm />
      <BulkAuthScreen
        onBack={() => void navigate({ href: appRoutes.accounts() })}
        onTestDcChange={(enabled) => void handleTestDcChange(enabled)}
        testDcEnabled={testDcEnabled}
        testDcPending={testDcPending}
      />
    </div>
  )
}
