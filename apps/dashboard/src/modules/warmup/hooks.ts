import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  createWarmupSession,
  deleteWarmupSession,
  fetchWarmupEvents,
  fetchWarmupReadiness,
  fetchWarmupSessions,
  fetchWarmupStrategies,
  pauseWarmupSession,
  resumeWarmupSession,
  validateWarmup,
} from './api'
import type { WarmupStatus } from './types'

const ACTIVE_STATUSES: WarmupStatus[] = ['validating', 'scheduled', 'active', 'paused_risk', 'paused_manual']

export const warmupQueryKeys = {
  readiness: ['warmup', 'readiness'] as const,
  strategies: ['warmup', 'strategies'] as const,
  sessions: ['warmup', 'sessions'] as const,
  events: (sessionId: string) => ['warmup', 'sessions', sessionId, 'events'] as const,
}

export function useWarmupReadiness() {
  return useQuery({
    queryKey: warmupQueryKeys.readiness,
    queryFn: fetchWarmupReadiness,
    refetchInterval: 60_000,
  })
}

export function useWarmupStrategies() {
  return useQuery({
    queryKey: warmupQueryKeys.strategies,
    queryFn: fetchWarmupStrategies,
  })
}

export function useWarmupSessions() {
  return useQuery({
    queryKey: warmupQueryKeys.sessions,
    queryFn: fetchWarmupSessions,
    refetchInterval: (query) => {
      const hasActive = query.state.data?.items.some((session) => ACTIVE_STATUSES.includes(session.status))
      return hasActive ? 10_000 : false
    },
  })
}

export function useWarmupEvents(sessionId: string | null) {
  return useQuery({
    queryKey: warmupQueryKeys.events(sessionId ?? 'none'),
    queryFn: () => fetchWarmupEvents(sessionId ?? ''),
    enabled: Boolean(sessionId),
  })
}

export function useWarmupValidate() {
  return useMutation({
    mutationFn: ({ accountId, strategyId }: { accountId: string; strategyId: string }) =>
      validateWarmup(accountId, strategyId),
  })
}

export function useCreateWarmupSession() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ accountId, strategyId }: { accountId: string; strategyId: string }) =>
      createWarmupSession(accountId, strategyId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: warmupQueryKeys.sessions })
    },
  })
}

export function usePauseWarmupSession() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ sessionId, reason }: { sessionId: string; reason: string }) => pauseWarmupSession(sessionId, reason),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: warmupQueryKeys.sessions })
    },
  })
}

export function useResumeWarmupSession() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ sessionId }: { sessionId: string }) => resumeWarmupSession(sessionId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: warmupQueryKeys.sessions })
    },
  })
}

export function useDeleteWarmupSession() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ sessionId }: { sessionId: string }) => deleteWarmupSession(sessionId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: warmupQueryKeys.sessions })
    },
  })
}
