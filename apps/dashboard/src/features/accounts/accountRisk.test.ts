import { describe, expect, test } from 'vitest'

import { EMPTY_ACCOUNT_RISK_SUMMARY, riskLevelFromScore } from '@/features/accounts/accountRisk'

describe('account risk UI helpers', () => {
  test('uses deterministic backend-compatible level thresholds', () => {
    expect(riskLevelFromScore(24)).toBe('low')
    expect(riskLevelFromScore(25)).toBe('medium')
    expect(riskLevelFromScore(60)).toBe('high')
    expect(riskLevelFromScore(80)).toBe('critical')
  })

  test('keeps the empty summary shape compatible with backend risk summary', () => {
    expect(EMPTY_ACCOUNT_RISK_SUMMARY).toMatchObject({
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
    })
  })
})
