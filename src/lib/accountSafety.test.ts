import { describe, expect, it } from 'vitest'

import {
  compactSafetyReasons,
  healthStatusLabel,
  riskLevelLabel,
  capabilityStateLabel,
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
})
