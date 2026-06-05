import { useEffect, useState } from 'react'

import type { WarmupSessionTimer as WarmupSessionTimerData } from '../types'

export function useElapsedSeconds(timer: WarmupSessionTimerData | null, now?: Date): number {
  const [clientNowMs, setClientNowMs] = useState(() => Date.now())

  useEffect(() => {
    if (now || timer?.status !== 'running') return
    const intervalId = window.setInterval(() => setClientNowMs(Date.now()), 1_000)
    return () => window.clearInterval(intervalId)
  }, [now, timer?.started_at, timer?.status])

  if (!timer) return 0
  if (timer.status !== 'running' || !timer.started_at) {
    return timer.elapsed_seconds
  }
  const nowMs = now ? now.getTime() : clientNowMs
  const startedAtMs = new Date(timer.started_at).getTime()
  if (!Number.isFinite(startedAtMs)) return timer.elapsed_seconds
  return Math.max(timer.elapsed_seconds, Math.floor((nowMs - startedAtMs) / 1000))
}

export function formatTimerText(elapsedSeconds: number, totalSeconds: number): string {
  return `${formatElapsedDuration(elapsedSeconds)} / ${formatTotalDuration(totalSeconds)}`
}

function formatElapsedDuration(seconds: number): string {
  const normalized = Math.max(0, Math.floor(seconds))
  if (normalized < 3600) {
    const minutes = Math.floor(normalized / 60)
    const remainder = normalized % 60
    return `${minutes}:${String(remainder).padStart(2, '0')}`
  }
  return formatTotalDuration(normalized)
}

function formatTotalDuration(seconds: number): string {
  const normalized = Math.max(0, Math.floor(seconds))
  const hours = Math.floor(normalized / 3600)
  const minutes = Math.floor((normalized % 3600) / 60)
  const remainder = normalized % 60
  return `${hours}:${String(minutes).padStart(2, '0')}:${String(remainder).padStart(2, '0')}`
}
