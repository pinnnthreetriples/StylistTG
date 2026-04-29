import { describe, expect, it } from 'vitest'

import { buildDiagnosticItems } from '@/lib/diagnostics'

describe('buildDiagnosticItems', () => {
  it('combines global and account diagnostics into stable UI items', () => {
    expect(
      buildDiagnosticItems(
        {
          database: 'ok',
          redis: 'down',
          tdlib: 'ok',
        },
        {
          account_id: 'account-1',
          account_state: 'execution_usable',
          runtime_health: 'manual_intervention_needed',
          reauth_required: true,
          authorized_last_confirmed_at: null,
          can_start_profile_job: false,
          last_error_code: 'FROZEN_METHOD_INVALID',
          last_error_class: 'runtime',
          tdlib_configured: true,
          manual_intervention_required: true,
          recovery_marker: 'tdlib_hard_stop:FROZEN_METHOD_INVALID',
          lock_owner: 'worker-1',
          lock_epoch: 3,
          diagnostic_timestamp: '2026-04-24T00:00:00Z',
        },
      ),
    ).toEqual([
      { key: 'database', label: 'Database', status: 'ok', message: 'Готова' },
      { key: 'redis', label: 'Redis', status: 'down', message: 'Недоступен' },
      { key: 'tdlib', label: 'TDLib', status: 'ok', message: 'Настроен' },
      {
        key: 'runtime',
        label: 'Runtime',
        status: 'attention',
        message: 'Нужна ручная проверка',
      },
      {
        key: 'last_error',
        label: 'Последняя ошибка',
        status: 'attention',
        message: 'Telegram ограничил это действие',
      },
      {
        key: 'safety',
        label: 'Safety',
        status: 'attention',
        message: 'Нужно ручное вмешательство',
      },
      {
        key: 'lock',
        label: 'Lock',
        status: 'attention',
        message: 'worker-1 #3',
      },
    ])
  })
})
