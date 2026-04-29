/**
 * Utilities for building dashboard-level banner messages from job state.
 *
 * Extracted from App.tsx to keep job-specific logic in the lib layer,
 * alongside the existing jobs.ts module.
 */

import type { JobDetail, JobStep } from '@/lib/api'
import { labelIssue } from '@/lib/uiLabels'
import type { RuntimeBanner } from '@/lib/dashboard'

export type { RuntimeBanner }

/**
 * Returns a banner describing a failed / partially-failed job, or null when
 * there is nothing worth surfacing to the user.
 */
export function buildJobBanner(
  job: JobDetail | null,
  steps: JobStep[],
): RuntimeBanner | null {
  if (!job) {
    return null
  }

  if (job.job_state === 'dedup_blocked') {
    return {
      title: 'Такая задача уже стоит в очереди',
      description: 'Повторный запуск с тем же набором изменений не нужен.',
      accent: 'warning' as const,
    }
  }

  const failingStep = steps.find((step) => step.error_code || step.uncertain_reason)
  if (!failingStep && !['failed', 'manual_intervention_needed', 'partially_completed'].includes(job.job_state)) {
    return null
  }

  const code = labelIssue(failingStep?.error_code ?? job.failure_reason ?? job.job_state)
  const description = failingStep?.uncertain_reason
    ? labelIssue(failingStep.uncertain_reason)
    : failingStep?.error_class
      ? labelIssue(failingStep.error_class)
      : job.failure_reason
        ? labelIssue(job.failure_reason)
        : 'Проверьте журнал шага и обновите runtime.'

  return {
    title: code,
    description,
    accent: 'error' as const,
  }
}

/**
 * Converts the internal FormState into the payload shape expected by the API.
 */
export function areStoryDraftsEqual(
  left: { draftId: string | null; assetId: string | null; action: string; caption: string; privacyPreset: string; activePeriodSeconds: number; protectContent: boolean }[],
  right: typeof left,
): boolean {
  if (left.length !== right.length) {
    return false
  }
  return left.every((story, index) => {
    const other = right[index]
    return (
      other &&
      story.draftId === other.draftId &&
      story.assetId === other.assetId &&
      story.action === other.action &&
      story.caption === other.caption &&
      story.privacyPreset === other.privacyPreset &&
      story.activePeriodSeconds === other.activePeriodSeconds &&
      story.protectContent === other.protectContent
    )
  })
}
