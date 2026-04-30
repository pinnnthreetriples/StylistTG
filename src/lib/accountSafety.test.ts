import { describe, expect, it } from 'vitest'

import {
  compactSafetyReasons,
  activeCooldownLabels,
  compactSafetyStatusLabel,
  cooldownSummaryLabel,
  healthStatusLabel,
  parseBackendTimestamp,
  riskLevelLabel,
  capabilityStateLabel,
  validityAgeLabel,
  validityStatusLabel,
  type AccountSafetySummary,
} from '@/lib/accountSafety'

describe('account safety labels', () => {
  it('maps safety states into Russian product labels', () => {
    expect(healthStatusLabel('ready')).toBe('Готов')
    expect(healthStatusLabel('attention')).toBe('Требует внимания')
    expect(healthStatusLabel('blocked')).toBe('Заблокирован')
    expect(healthStatusLabel('unknown')).toBe('Неизвестно')

    expect(riskLevelLabel('low')).toBe('Низкий риск')
    expect(riskLevelLabel('medium')).toBe('Средний риск')
    expect(riskLevelLabel('high')).toBe('Высокий риск')
    expect(riskLevelLabel('blocked')).toBe('Заблокировано')
    expect(capabilityStateLabel('limited')).toBe('Ограничено')
    expect(validityStatusLabel(null)).toBe('Проверка ещё не запускалась')
    expect(validityStatusLabel({ status: 'completed' } as never)).toBe('Проверено по данным приложения')
  })

  it('keeps compact reasons bounded for account cards', () => {
    const safety: AccountSafetySummary = {
      account_id: 'account-1',
      health_status: 'attention',
      overall_risk_level: 'medium',
      validity_status: 'db_snapshot',
      capability_summary: {
        profile_text: 'available',
        username: 'limited',
      },
      cooldown_summary: [],
      top_reasons: [
        { code: 'stale_profile_sync', severity: 'medium', source: 'profile_sync', message: 'Профиль давно не синхронизировался', last_seen_at: null },
        { code: 'recent_partial_job', severity: 'medium', source: 'job', message: 'Недавно задача завершилась частично', last_seen_at: null },
      ],
      last_checked_at: '2026-04-30T00:00:00Z',
      source: 'db_snapshot',
    }

    expect(compactSafetyReasons(safety)).toEqual([
      'Профиль давно не синхронизировался',
      'Недавно задача завершилась частично',
    ])
  })

  it('summarizes active operation cooldowns for cards and header', () => {
    const now = Date.now()
    const retryAfter = new Date(now + 14 * 60_000).toISOString()
    const safety: AccountSafetySummary = {
      account_id: 'account-1',
      health_status: 'ready',
      overall_risk_level: 'medium',
      validity_status: 'valid',
      capability_summary: {},
      cooldown_summary: [
        {
          id: 'cooldown-1',
          account_id: 'account-1',
          operation: 'username',
          level: 'blocked',
          reason_code: 'recent_flood_wait',
          started_at: '2026-04-30T00:00:00Z',
          retry_after_at: retryAfter,
          source: 'job_step_result',
          source_job_id: 'job-1',
          source_step_id: 'step-1',
        },
      ],
      top_reasons: [],
      last_checked_at: '2026-04-30T00:00:00Z',
      source: 'db_snapshot',
    }

    expect(cooldownSummaryLabel(safety.cooldown_summary[0], now)).toBe('Username: через 14 мин')
    expect(activeCooldownLabels(safety)).toEqual(['Username: через 14 мин'])
    expect(compactSafetyStatusLabel(safety)).toBe('На паузе')
  })

  it('treats backend timestamps without timezone as UTC', () => {
    const now = Date.parse('2026-04-30T11:00:20Z')
    expect(parseBackendTimestamp('2026-04-30T11:00:00')).toBe(Date.parse('2026-04-30T11:00:00Z'))
    expect(
      validityAgeLabel(
        {
          id: 'check-1',
          account_id: 'account-1',
          mode: 'tdlib_readonly',
          status: 'completed',
          started_at: '2026-04-30T11:00:00',
          finished_at: '2026-04-30T11:00:00',
          error_code: null,
          error_class: null,
          details: null,
          result: { validity_status: 'valid' },
          created_at: '2026-04-30T11:00:00',
        },
        now,
      ),
    ).toBe('Проверено только что')
  })
})
