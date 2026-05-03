import { describe, expect, test } from 'vitest'

import { buildAccountRisk, riskLevelFromScore, summarizeAccountRisks } from '@/features/accounts/accountRisk'
import type { AccountListItem } from '@/lib/api'

const baseAccount: AccountListItem = {
  account_id: 'acc_1',
  display_name: 'Demo',
  username: 'demo',
  phone_number: '+10000000000',
  telegram_user_id: null,
  account_state: 'execution_usable',
  runtime_health: 'ready',
  is_execution_usable: true,
  is_test_dc: false,
  profile_photo_asset_id: null,
  updated_at: '2026-05-02T00:00:00Z',
}

describe('account risk scoring', () => {
  test('scores healthy accounts as low risk', () => {
    const risk = buildAccountRisk(baseAccount)

    expect(risk.level).toBe('low')
    expect(risk.reasons.some((reason) => reason.code === 'ready')).toBe(false)
    expect(risk.reasons.some((reason) => reason.code === 'safety_unchecked')).toBe(true)
  })

  test('scores non-ready accounts as high or critical with stable reasons', () => {
    const risk = buildAccountRisk({
      ...baseAccount,
      account_state: 'reauth_required',
      runtime_health: 'manual_intervention_needed',
      is_execution_usable: false,
    })

    expect(risk.level).toBe('critical')
    expect(risk.reasons.map((reason) => reason.code)).toContain('reauth_required')
    expect(risk.reasons.map((reason) => reason.code)).toContain('runtime_not_ready')
  })

  test('summarizes risk counts for Health Center', () => {
    const summary = summarizeAccountRisks([
      { score: 5, level: 'low', reasons: [], recommendedAction: 'none' },
      { score: 85, level: 'critical', reasons: [{ code: 'proxy_problem', severity: 'warning', message: 'Proxy failed' }] },
    ])

    expect(summary.total).toBe(2)
    expect(summary.low).toBe(1)
    expect(summary.critical).toBe(1)
    expect(summary.proxyProblems).toBe(1)
  })

  test('uses deterministic level thresholds', () => {
    expect(riskLevelFromScore(24)).toBe('low')
    expect(riskLevelFromScore(25)).toBe('medium')
    expect(riskLevelFromScore(60)).toBe('high')
    expect(riskLevelFromScore(80)).toBe('critical')
  })
})
