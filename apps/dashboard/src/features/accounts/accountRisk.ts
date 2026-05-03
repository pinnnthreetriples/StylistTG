import type { AccountListItem, AccountProxySummary } from '@/lib/api'
import type { AccountSafetySummary } from '@/lib/accountSafety'

export type AccountRiskLevel = 'low' | 'medium' | 'high' | 'critical'

export type AccountRiskReason = {
  code: string
  severity: 'info' | 'warning' | 'critical'
  message: string
}

export type AccountRisk = {
  score: number
  level: AccountRiskLevel
  reasons: AccountRiskReason[]
  recommendedAction?: string
}

export type AccountRiskSummary = {
  total: number
  low: number
  medium: number
  high: number
  critical: number
  requiringReauth: number
  withoutSession: number
  proxyProblems: number
}

export function buildAccountRisk(
  account: AccountListItem,
  safety?: AccountSafetySummary | null,
  proxy?: AccountProxySummary | null,
): AccountRisk {
  const reasons: AccountRiskReason[] = []
  let score = 0

  if (!account.is_execution_usable || account.account_state.includes('reauth') || account.account_state.includes('login')) {
    score += 55
    reasons.push({
      code: 'reauth_required',
      severity: 'critical',
      message: 'Account is not execution-usable and may require reauthorization.',
    })
  }

  if (account.runtime_health !== 'ready') {
    score += 30
    reasons.push({
      code: 'runtime_not_ready',
      severity: 'critical',
      message: `Runtime health is ${account.runtime_health}.`,
    })
  }

  if (proxy && ['failed', 'error', 'tdlib_failed'].includes(proxy.status)) {
    score += 20
    reasons.push({
      code: 'proxy_problem',
      severity: 'warning',
      message: 'Proxy diagnostics report a connectivity problem.',
    })
  }

  const safetyRiskLevel = String(safety?.overall_risk_level ?? '')
  if (safetyRiskLevel === 'critical' || safetyRiskLevel === 'blocked') {
    score += 35
    reasons.push({
      code: 'safety_critical',
      severity: 'critical',
      message: 'Account safety summary contains critical blockers.',
    })
  } else if (safetyRiskLevel === 'high') {
    score += 25
    reasons.push({
      code: 'safety_high',
      severity: 'warning',
      message: 'Account safety summary contains high-risk signals.',
    })
  } else if (safetyRiskLevel === 'medium') {
    score += 12
    reasons.push({
      code: 'safety_medium',
      severity: 'warning',
      message: 'Account safety summary contains warnings.',
    })
  }

  if ((safety?.cooldown_summary?.length ?? 0) > 0) {
    score += 18
    reasons.push({
      code: 'cooldown_active',
      severity: 'warning',
      message: 'One or more operation cooldowns are active.',
    })
  }

  if (!safety) {
    score += 10
    reasons.push({
      code: 'safety_unchecked',
      severity: 'info',
      message: 'Safety summary has not been loaded yet.',
    })
  }

  const normalizedScore = Math.min(100, score)
  const level = riskLevelFromScore(normalizedScore)

  if (reasons.length === 0) {
    reasons.push({
      code: 'ready',
      severity: 'info',
      message: 'No app-known readiness risks are currently visible.',
    })
  }

  return {
    score: normalizedScore,
    level,
    reasons,
    recommendedAction: recommendedAction(level),
  }
}

export function summarizeAccountRisks(risks: AccountRisk[]): AccountRiskSummary {
  return risks.reduce<AccountRiskSummary>(
    (summary, risk) => {
      summary.total += 1
      summary[risk.level] += 1
      if (risk.reasons.some((reason) => reason.code === 'reauth_required')) summary.requiringReauth += 1
      if (risk.reasons.some((reason) => reason.code === 'runtime_not_ready')) summary.withoutSession += 1
      if (risk.reasons.some((reason) => reason.code === 'proxy_problem')) summary.proxyProblems += 1
      return summary
    },
    { total: 0, low: 0, medium: 0, high: 0, critical: 0, requiringReauth: 0, withoutSession: 0, proxyProblems: 0 },
  )
}

export function riskLevelFromScore(score: number): AccountRiskLevel {
  if (score >= 80) return 'critical'
  if (score >= 60) return 'high'
  if (score >= 25) return 'medium'
  return 'low'
}

function recommendedAction(level: AccountRiskLevel): string {
  if (level === 'critical') return 'Review authorization/runtime state before any operation.'
  if (level === 'high') return 'Check readiness, proxy, and recent safety blockers.'
  if (level === 'medium') return 'Review warnings before batch actions.'
  return 'No action required for app-known readiness.'
}
