import { useCallback, useEffect, useState } from 'react'

import { fetchAuthRuntimeMode, updateAuthRuntimeMode } from '@/lib/auth'
import { AddAccountsPage } from '@/features/accounts/AddAccountsPage'

export function AuthBatchRoute() {
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
    <AddAccountsPage
      onTestDcChange={(enabled) => void handleTestDcChange(enabled)}
      testDcEnabled={testDcEnabled}
      testDcPending={testDcPending}
    />
  )
}
