import { describe, expect, test } from 'vitest'

import { canSubmitDeletionRequest } from './deleteAccountSubmit'

const validInput = {
  confirmation: 'DELETE',
  isPreviewError: false,
  isPreviewPending: false,
  isSubmitting: false,
  preview: { can_delete: true },
  reason: 'valid reason',
}

describe('canSubmitDeletionRequest', () => {
  test('blocks submit while deletion preview is loading', () => {
    expect(
      canSubmitDeletionRequest({
        ...validInput,
        isPreviewPending: true,
        preview: undefined,
      }),
    ).toBe(false)
  })

  test('blocks submit when deletion preview failed', () => {
    expect(
      canSubmitDeletionRequest({
        ...validInput,
        isPreviewError: true,
        preview: undefined,
      }),
    ).toBe(false)
  })

  test('blocks submit when deletion preview rejects deletion', () => {
    expect(
      canSubmitDeletionRequest({
        ...validInput,
        preview: { can_delete: false },
      }),
    ).toBe(false)
  })

  test('allows submit only after successful positive preview and valid confirmation', () => {
    expect(canSubmitDeletionRequest(validInput)).toBe(true)
  })
})
