import type { SafetyGateIntent } from '@/lib/api'

export const queryKeys = {
  currentUser: ['currentUser'] as const,
  accounts: ['accounts'] as const,
  accountSafety: {
    root: ['accountSafety'] as const,
    summary: ['accountSafety', 'summary'] as const,
    account: (accountId: string) => ['accountSafety', accountId] as const,
    gate: (accountId: string, intent: SafetyGateIntent) => ['accountSafety', accountId, 'gate', intent] as const,
    checks: (accountId: string) => ['accountSafety', accountId, 'checks'] as const,
    batchPreview: (operation: string, accountIds: string[]) =>
      ['accountSafety', 'batchPreview', operation, [...accountIds].sort().join(',')] as const,
    batchPreviewWithOverride: (operation: string, accountIds: string[], allowWarningOverrides: boolean) =>
      ['accountSafety', 'batchPreview', operation, [...accountIds].sort().join(','), allowWarningOverrides] as const,
  },
  accountRisk: {
    summary: ['accountRisk', 'summary'] as const,
    account: (accountId: string) => ['accountRisk', accountId] as const,
    actionGate: (accountId: string, actionType: string) => ['accountRisk', accountId, 'actionGate', actionType] as const,
  },
  accountLifecycle: {
    deletionPreview: (accountId: string) => ['accountLifecycle', accountId, 'deletionPreview'] as const,
    deletionRequests: (accountId: string) => ['accountLifecycle', accountId, 'deletionRequests'] as const,
    exportRequests: (accountId: string) => ['accountLifecycle', accountId, 'exportRequests'] as const,
    cooldowns: (accountId: string) => ['accountLifecycle', accountId, 'cooldowns'] as const,
  },
  proxy: {
    summary: ['proxy', 'summary'] as const,
    account: (accountId: string) => ['proxy', accountId] as const,
  },
  operationLogs: {
    global: ['operationLogs', 'global'] as const,
    account: (accountId: string) => ['operationLogs', accountId] as const,
  },
  audit: {
    global: ['audit', 'global'] as const,
    account: (accountId: string) => ['audit', accountId] as const,
  },
  workers: {
    diagnostics: ['workers', 'diagnostics'] as const,
    jobPolicies: ['workers', 'jobPolicies'] as const,
  },
  tdlibRuntime: ['tdlibRuntime'] as const,
  telegramAuth: {
    sessions: ['telegramAuth', 'sessions'] as const,
    session: (authSessionId: string) => ['telegramAuth', 'sessions', authSessionId] as const,
  },
  accountImport: {
    batches: ['accountImport', 'batches'] as const,
    batch: (batchId: string) => ['accountImport', 'batches', batchId] as const,
  },
  authState: (accountId: string) => ['authState', accountId] as const,
  settings: {
    root: ['settings'] as const,
    bundle: ['settings', 'bundle'] as const,
    runtime: ['settings', 'runtime'] as const,
    preflight: ['settings', 'preflight'] as const,
    policy: ['settings', 'policy'] as const,
    safetyPolicy: ['settings', 'safetyPolicy'] as const,
    authMode: ['settings', 'authMode'] as const,
    frontendDiagnostics: ['settings', 'frontendDiagnostics'] as const,
  },
  dashboard: {
    root: ['dashboard'] as const,
    disasterState: ['dashboard', 'disasterState'] as const,
    account: (accountId: string) => ['dashboard', accountId] as const,
    profile: (accountId: string) => ['dashboard', accountId, 'profile'] as const,
    jobs: (accountId: string) => ['dashboard', accountId, 'jobs'] as const,
    latestJob: (accountId: string) => ['dashboard', accountId, 'latestJob'] as const,
    storyDrafts: (accountId: string) => ['dashboard', accountId, 'storyDrafts'] as const,
    storyCapabilities: (accountId: string) => ['dashboard', accountId, 'storyCapabilities'] as const,
    bundle: (accountId: string) => ['dashboard', accountId, 'bundle'] as const,
  },
  job: {
    detail: (jobId: string) => ['job', jobId] as const,
    steps: (jobId: string) => ['job', jobId, 'steps'] as const,
    stateBundle: (jobId: string) => ['job', jobId, 'stateBundle'] as const,
  },
}
