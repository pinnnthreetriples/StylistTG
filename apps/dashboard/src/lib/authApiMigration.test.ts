import { describe, expect, test } from 'vitest'

import * as auth from '@/lib/auth'
import * as authBatches from '@/lib/authBatches'

describe('auth API migration', () => {
  test('auth modules expose api-client backed network functions', () => {
    expect(String(auth.startOtp)).not.toContain('apiRequest')
    expect(String(auth.confirmOtp)).not.toContain('apiRequest')
    expect(String(auth.fetchAuthState)).not.toContain('apiRequest')
    expect(String(authBatches.validateAuthBatchPhones)).not.toContain('apiRequest')
    expect(String(authBatches.createAuthBatch)).not.toContain('apiRequest')
    expect(String(authBatches.pollAuthBatch)).not.toContain('apiRequest')
  })
})
