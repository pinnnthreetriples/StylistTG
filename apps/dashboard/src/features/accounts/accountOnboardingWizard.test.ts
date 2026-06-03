import { describe, expect, test } from 'vitest'

import { parseOnboardingPhones } from '@/features/accounts/accountOnboardingWizard'

describe('parseOnboardingPhones', () => {
  test('parses single and pasted bulk phones without making the second phone a label', () => {
    const rows = parseOnboardingPhones('+1 (555) 010-2000 Alice\n+15550102001; +15550102002', 'Batch')

    expect(rows).toEqual([
      { phone_number: '+15550102000', label: 'Alice', position: 0, raw: '+1 (555) 010-2000' },
      { phone_number: '+15550102001', label: 'Batch', position: 1, raw: '+15550102001' },
      { phone_number: '+15550102002', label: 'Batch', position: 2, raw: '+15550102002' },
    ])
  })
})

