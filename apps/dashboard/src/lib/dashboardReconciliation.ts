import {
  areDashboardFormStatesEqual,
  reconcileStoredDashboardFormDraft,
  type FormState,
} from '@/lib/dashboard'
import { areStoryDraftsEqual } from '@/lib/jobBanner'

export type DashboardFormReconciliation = {
  nextForm: FormState | null
  nextBaseline: FormState | null
  draftToPersist: FormState | null
  shouldClearDraft: boolean
}

export function reconcileDashboardFormState({
  currentBaseline,
  currentForm,
  formInitialized,
  resetForm,
  serverForm,
  storedDraft,
}: {
  currentBaseline: FormState | null
  currentForm: FormState
  formInitialized: boolean
  resetForm?: boolean
  serverForm: FormState
  storedDraft: FormState | null
}): DashboardFormReconciliation {
  const reconciledStoredDraft = storedDraft
    ? reconcileStoredDashboardFormDraft(storedDraft, serverForm)
    : null
  const isDirty = currentBaseline ? !areDashboardFormStatesEqual(currentForm, currentBaseline) : false
  const shouldResetForm = resetForm ?? (!formInitialized || !isDirty)

  if (shouldResetForm) {
    const nextForm = !resetForm && reconciledStoredDraft ? reconciledStoredDraft : serverForm
    return {
      nextForm,
      nextBaseline: serverForm,
      draftToPersist: reconciledStoredDraft && !resetForm ? reconciledStoredDraft : null,
      shouldClearDraft: !reconciledStoredDraft || Boolean(resetForm),
    }
  }

  if (!areStoryDraftsEqual(currentForm.stories, serverForm.stories)) {
    const nextForm = { ...currentForm, stories: serverForm.stories }
    return {
      nextForm,
      nextBaseline: null,
      draftToPersist: nextForm,
      shouldClearDraft: false,
    }
  }

  return {
    nextForm: null,
    nextBaseline: null,
    draftToPersist: null,
    shouldClearDraft: false,
  }
}
