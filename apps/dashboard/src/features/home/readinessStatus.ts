import type { StatusPillTone } from '@stylisttg/ui'

export type ReadyLike = {
  status?: string | null
} | null | undefined

export type HomeReadinessStatus = {
  tone: StatusPillTone
  label: string
}

export function getHomeApiReadinessStatus(ready: ReadyLike, isError: boolean): HomeReadinessStatus {
  if (isError) {
    return { tone: 'red', label: 'Недоступен' }
  }
  if (!ready) {
    return { tone: 'muted', label: 'Проверка...' }
  }
  if (ready.status === 'ok') {
    return { tone: 'green', label: 'Работает' }
  }
  return { tone: 'red', label: 'Недоступен' }
}
