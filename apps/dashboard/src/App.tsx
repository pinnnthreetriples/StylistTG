// fallow-ignore-file complexity
// fallow-ignore-reason: App-level route composition root; feature logic lives in split modules and hooks.
/**
 * App – root application controller for account workspace.
 *
 * Responsibilities:
 *  - Composing hooks (useAuthFlow, useDashboard, useProfileDraft, useDashboardActions)
 *  - Managing auth/dashboard phase transitions
 *  - Delegating rendering to AuthScreen or AccountDashboardView
 */

import { useQueryClient } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { useCallback, useTransition } from 'react'

import { AuthScreen } from '@/components/auth/AuthScreen'
import { DashboardSkeleton } from '@/components/dashboard/DashboardSkeleton'
import { ToastProvider, useToast } from '@/providers/ToastProvider'
import { getPollingIntervalMs } from '@/lib/config'
import { useDashboardInitialState } from '@/hooks/useDashboardInitialState'
import { useAuthFlow, type AuthPhase } from '@/modules/auth'
import type { AppRouteState } from '@/lib/routes'
import { AccountWorkspace } from '@/app/AccountWorkspace'

const JOB_POLLING_INTERVAL_MS = getPollingIntervalMs()
type AccountRouteState = Extract<AppRouteState, { screen: 'account' }>

function initialAuthPhaseForRoute(hasInitialDashboard: boolean): AuthPhase {
  return hasInitialDashboard ? 'dashboard' : 'auth-loading'
}

function toVisibleAuthPhase(
  phase: AuthPhase,
): 'auth-loading' | 'auth-phone' | 'auth-code' | 'auth-password' | 'auth-refreshing' | 'auth-error' {
  if (phase === 'dashboard') return 'auth-loading'
  return phase
}

function AppInner({ route }: { route: AccountRouteState }) {
  const { notify } = useToast()
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [, startNavigationTransition] = useTransition()
  const activeAccountId = route.accountId
  const { initialAccountId, initialBundle, initialDashboard, initialForm } = useDashboardInitialState(route.accountId, queryClient)

  const auth = useAuthFlow({
    initialAccountId,
    initialPhase: initialAuthPhaseForRoute(Boolean(initialDashboard)),
  } as Parameters<typeof useAuthFlow>[0])
  const {
    authPhase,
    authStep,
    accountId,
    phoneNumber,
    otpCode,
    twoFaPassword,
    passwordHint,
    authError,
    authErrorCode,
    testDcEnabled,
    isUpdatingTestDc,
    setAuthPhase,
    setOtpCode,
    setTwoFaPassword,
    setPhoneNumber,
    setAuthError,
    setAuthErrorCode,
    setAuthStep,
    handleStartOtp,
    handleConfirmOtp,
    handleSubmitPassword,
    handleResetAuthPhone,
    handleTestDcChange,
    applyAuthStateResponse,
    applyAccountContext,
    clearAccountContext,
    _skipNextBootstrapRef: skipNextAuthBootstrapRef,
  } = auth as typeof auth & { _skipNextBootstrapRef: React.MutableRefObject<boolean> }

  const transitionToPhase = useCallback(
    (phase: AuthPhase) => {
      startNavigationTransition(() => setAuthPhase(phase))
    },
    [setAuthPhase],
  )

  const navigateToRoute = useCallback(
    (href: string) => {
      void navigate({ href })
    },
    [navigate],
  )

  if (accountId !== route.accountId) {
    return <DashboardSkeleton />
  }

  if (authPhase === 'auth-loading' && activeAccountId) {
    return <DashboardSkeleton />
  }

  if (authPhase !== 'dashboard') {
    return (
      <AuthScreen
        code={otpCode}
        password={twoFaPassword}
        passwordHint={passwordHint}
        errorCode={authErrorCode}
        errorMessage={authError}
        testDcEnabled={testDcEnabled}
        testDcPending={isUpdatingTestDc}
        onCodeChange={setOtpCode}
        onPasswordChange={setTwoFaPassword}
        onConfirm={handleConfirmOtp}
        onSubmitPassword={handleSubmitPassword}
        onPhoneNumberChange={setPhoneNumber}
        onResetPhone={handleResetAuthPhone}
        onStart={handleStartOtp}
        onTestDcChange={handleTestDcChange}
        phase={toVisibleAuthPhase(authPhase)}
        phoneNumber={phoneNumber}
        step={authStep}
      />
    )
  }

  return (
    <AccountWorkspace
      activeAccountId={activeAccountId}
      auth={{
        accountId,
        applyAccountContext,
        applyAuthStateResponse,
        clearAccountContext,
        setAuthError,
        setAuthErrorCode,
        setAuthPhase,
        setAuthStep,
        setOtpCode,
        setPhoneNumber,
        setTwoFaPassword,
        skipNextAuthBootstrapRef,
      }}
      authPhase={authPhase}
      initialBundle={initialBundle}
      initialDashboard={initialDashboard}
      initialForm={initialForm}
      navigateToRoute={navigateToRoute}
      notify={notify}
      pollingIntervalMs={JOB_POLLING_INTERVAL_MS}
      queryClient={queryClient}
      route={route}
      transitionToPhase={transitionToPhase}
    />
  )
}

function App({ route }: { route: AccountRouteState }) {
  return (
    <ToastProvider>
      <AppInner route={route} />
    </ToastProvider>
  )
}

export default App
