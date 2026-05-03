import type { AccountReadinessRisk, AccountReadinessRiskSummary } from '@/lib/api'

export type AccountRiskLevel = AccountReadinessRisk['level']
export type AccountRisk = AccountReadinessRisk
export type AccountRiskSummary = AccountReadinessRiskSummary

export function riskLevelFromScore(score: number): AccountRiskLevel {
  if (score >= 80) return 'critical'
  if (score >= 60) return 'high'
  if (score >= 25) return 'medium'
  return 'low'
}

export const EMPTY_ACCOUNT_RISK_SUMMARY: AccountRiskSummary = {
  total: 0,
  low: 0,
  medium: 0,
  high: 0,
  critical: 0,
  reauth_required: 0,
  missing_session: 0,
  runtime_unhealthy: 0,
  proxy_problem: 0,
  items: [],
  computed_at: '',
}
