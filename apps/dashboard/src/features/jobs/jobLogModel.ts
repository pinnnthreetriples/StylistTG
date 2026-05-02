export type JobLogEntry = {
  id: string
  timestamp: string
  level: 'info' | 'warning' | 'error'
  message: string
}

export function createDemoJobLogRows(count = 750): JobLogEntry[] {
  return Array.from({ length: count }, (_, index) => ({
    id: `demo-log-${index + 1}`,
    timestamp: new Date(Date.UTC(2026, 4, 2, 10, index % 60, index % 60)).toISOString(),
    level: index % 17 === 0 ? 'warning' : 'info',
    message: `Mock worker event ${index + 1}: profile_jobs/auth_jobs listener heartbeat`,
  }))
}
