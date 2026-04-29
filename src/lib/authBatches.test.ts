import { describe, expect, it } from 'vitest'

import {
  buildAuthBatchPrimaryActionLabel,
  buildAuthBatchValidationMessage,
  buildBackendValidItemLines,
  labelAuthBatchItemStatus,
  labelAuthBatchStatus,
  parseBulkPhoneLines,
  parseBulkPhones,
  sanitizeBulkPhoneInput,
  uniqueBulkPhoneLines,
  type AuthBatchValidation,
} from '@/lib/authBatches'

function validation(overrides: Partial<AuthBatchValidation>): AuthBatchValidation {
  return {
    valid_items: [],
    invalid_items: [],
    duplicates: [],
    existing_accounts: [],
    active_batch_conflicts: [],
    ...overrides,
  }
}

describe('auth batch helpers', () => {
  it('parses phone lines with optional labels', () => {
    expect(parseBulkPhones('+79991234567\n79997654321, Марина')).toEqual([
      { phone_number: '+79991234567', label: null },
      { phone_number: '+79997654321', label: 'Марина' },
    ])
  })

  it('keeps non-phone lines out of backend payload', () => {
    expect(parseBulkPhones('89991234567\nhello\n79991234567')).toEqual([
      { phone_number: '+79991234567', label: null },
      { phone_number: '+79991234567', label: null },
    ])
  })

  it('sanitizes phone input while keeping labels after comma', () => {
    expect(sanitizeBulkPhoneInput('abc+7 (999) 111-22-33, Марина!\n79997654321')).toBe(
      '+79991112233, Марина!\n+79997654321',
    )
  })

  it('adds plus automatically for every numeric phone line', () => {
    expect(sanitizeBulkPhoneInput('573180030191\n999')).toBe('+573180030191\n+999')
    expect(sanitizeBulkPhoneInput('+')).toBe('+')
  })

  it('converts Russian 8-prefix numbers in the form instead of showing an error', () => {
    expect(sanitizeBulkPhoneInput('89991234567')).toBe('+79991234567')
    expect(parseBulkPhoneLines('89991234567')).toMatchObject([
      { position: 0, status: 'valid', phone_number: '+79991234567' },
    ])
  })

  it('limits phone digits in the form instead of showing a too-long error', () => {
    expect(sanitizeBulkPhoneInput('+7999123456789012345')).toBe('+799912345678901')
    expect(parseBulkPhoneLines('+7999123456789012345')).toMatchObject([
      { position: 0, status: 'valid', phone_number: '+799912345678901' },
    ])
  })

  it('reports short rows as line errors', () => {
    expect(parseBulkPhoneLines('+7999')).toMatchObject([
      { position: 0, status: 'invalid', error: 'Короткий номер' },
    ])
  })

  it('builds compact line actions for unique and backend-new rows', () => {
    const lines = parseBulkPhoneLines('+79991234567\n79991234567, дубль\n79997654321, Марина')
    expect(uniqueBulkPhoneLines(lines)).toEqual(['+79991234567', '+79997654321, Марина'])
    expect(
      buildBackendValidItemLines(
        validation({
          valid_items: [{ phone_number: '+79997654321', label: 'Марина', position: 2 }],
        }),
      ),
    ).toEqual(['+79997654321, Марина'])
  })

  it('labels batch and item statuses in Russian', () => {
    expect(labelAuthBatchItemStatus('waiting_code')).toBe('Ожидает код')
    expect(labelAuthBatchItemStatus('waiting_2fa')).toBe('Ожидает 2FA')
    expect(labelAuthBatchItemStatus('queued')).toBe('В очереди')
    expect(labelAuthBatchItemStatus('starting')).toBe('Запуск')
    expect(labelAuthBatchItemStatus('skipped')).toBe('Пропущен')
    expect(labelAuthBatchStatus('pending')).toBe('Ожидает запуска')
    expect(labelAuthBatchStatus('running')).toBe('В работе')
    expect(labelAuthBatchStatus('completed')).toBe('Завершено')
  })

  it('uses a singular primary action for one parsed phone', () => {
    expect(buildAuthBatchPrimaryActionLabel(0)).toBe('Добавить аккаунты')
    expect(buildAuthBatchPrimaryActionLabel(1)).toBe('Добавить аккаунт')
    expect(buildAuthBatchPrimaryActionLabel(2)).toBe('Добавить аккаунты')
  })

  it('explains existing-only validation results before creating a batch', () => {
    expect(
      buildAuthBatchValidationMessage(
        validation({
          existing_accounts: [
            {
              phone_number: '+573209711301',
              label: null,
              position: 0,
              account_id: 'account-1',
              batch_item_id: null,
              batch_id: null,
            },
          ],
        }),
      ),
    ).toBe('Такой аккаунт уже есть. Введите новый номер или откройте существующий аккаунт в списке.')
  })

  it('allows launch when validation contains at least one new account', () => {
    expect(
      buildAuthBatchValidationMessage(
        validation({
          valid_items: [{ phone_number: '+573180030191', label: null, position: 0 }],
        }),
      ),
    ).toBeNull()
  })

  it('explains active batch conflicts as resumable auth', () => {
    expect(
      buildAuthBatchValidationMessage(
        validation({
          active_batch_conflicts: [
            {
              phone_number: '+573180030191',
              label: null,
              position: 0,
              account_id: 'account-1',
              batch_item_id: 'item-1',
              batch_id: 'batch-1',
            },
          ],
        }),
      ),
    ).toBe('По этому номеру уже идёт авторизация. Открываю активную пачку.')
  })
})
