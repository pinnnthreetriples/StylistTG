type JobStateLike = {
  job_state: string
}

export function buildJobMetrics(jobs: JobStateLike[]): {
  total: number
  success: number
  issues: number
} {
  const materialJobs = jobs.filter((job) => job.job_state !== 'dedup_blocked')
  return {
    total: materialJobs.length,
    success: materialJobs.filter((job) => job.job_state === 'completed').length,
    issues: materialJobs.filter((job) =>
      ['failed', 'manual_intervention_needed', 'partially_completed', 'canceled'].includes(job.job_state),
    ).length,
  }
}
