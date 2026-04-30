import { describe, expect, it } from 'vitest'

import { compactOperationLogLabel, operationStatusLabel, operationTypeLabel } from '@/lib/operationLogs'

describe('operation log labels', () => {
  it('maps operation events to compact Russian labels', () => {
    expect(operationTypeLabel('validity_check')).toBe('Проверка аккаунта')
    expect(operationStatusLabel('completed')).toBe('Успешно')
    expect(
      compactOperationLogLabel({
        id: 'log-1',
        account_id: 'account-1',
        operation_type: 'proxy',
        operation_key: 'check_proxy',
        status: 'failed',
        severity: 'warning',
        source: 'test',
        message: 'failed',
        error_code: 'proxy_timeout',
        error_class: 'proxy',
        metadata: {},
        request_id: null,
        job_id: null,
        step_id: null,
        created_at: '2026-04-30T10:00:00Z',
      }),
    ).toBe('Проверка proxy — Ошибка')
  })
})
