import type { AccountDeletionPreview } from '@/lib/api'

export function canSubmitDeletionRequest({
  confirmation,
  isPreviewError,
  isPreviewPending,
  isSubmitting,
  preview,
  reason,
}: {
  confirmation: string
  isPreviewError: boolean
  isPreviewPending: boolean
  isSubmitting: boolean
  preview: Pick<AccountDeletionPreview, 'can_delete'> | undefined
  reason: string
}) {
  return (
    confirmation === 'DELETE' &&
    reason.trim().length >= 10 &&
    preview?.can_delete === true &&
    !isPreviewPending &&
    !isPreviewError &&
    !isSubmitting
  )
}
