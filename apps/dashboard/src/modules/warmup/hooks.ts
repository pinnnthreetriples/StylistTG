import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useState } from 'react'

import {
  applyWarmupActionPreset,
  createCyclicWarmupSessions,
  createWarmupSession,
  deleteWarmupSession,
  fetchWarmupActionMetadata,
  fetchWarmupEvents,
  fetchWarmupLiveEvents,
  fetchWarmupIsolationStatus,
  fetchWarmupReadiness,
  fetchWarmupSessionDetail,
  fetchWarmupSessions,
  fetchWarmupStrategies,
  pauseWarmupSession,
  resumeWarmupSession,
  updateWarmupDisabledActions,
  validateWarmup,
} from './api'
import type {
  WarmupActionPreset,
  WarmupEventPage,
  WarmupLiveEventFilters,
  WarmupLiveEventPage,
  WarmupPresetKind,
  WarmupSessionDetail,
  WarmupSessionPage,
  WarmupStatus,
} from './types'

export const ACTIVE_STATUSES: WarmupStatus[] = ['validating', 'scheduled', 'active', 'paused_risk', 'paused_manual']

export const warmupQueryKeys = {
  readiness: ['warmup', 'readiness'] as const,
  actionMetadata: ['warmup', 'actions', 'metadata'] as const,
  strategies: ['warmup', 'strategies'] as const,
  sessions: ['warmup', 'sessions'] as const,
  sessionDetail: (sessionId: string) => ['warmup', 'sessions', sessionId, 'detail'] as const,
  events: (sessionId: string) => ['warmup', 'sessions', sessionId, 'events'] as const,
  liveEvents: (filters: WarmupLiveEventFilters) => [
    'warmup',
    'events',
    filters.accountId ?? 'all',
    filters.severity ?? 'all',
    filters.limit ?? 100,
  ] as const,
  isolation: (accountId: string) => ['warmup', 'isolation', accountId] as const,
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

export function useWarmupActionMetadata() {
  return useQuery({
    queryKey: warmupQueryKeys.actionMetadata,
    queryFn: fetchWarmupActionMetadata,
    staleTime: 5 * 60_000,
  })
}

export function useWarmupSessions() {
  return useQuery<WarmupSessionPage>({
    queryKey: warmupQueryKeys.sessions,
    queryFn: () => fetchWarmupSessions(),
    refetchInterval: (query) => {
      const hasActive = query.state.data?.items.some((session) => ACTIVE_STATUSES.includes(session.status))
      return hasActive ? 10_000 : false
    },
  })
}

export function useWarmupEvents(sessionId: string | null) {
  return useQuery<WarmupEventPage>({
    queryKey: warmupQueryKeys.events(sessionId ?? '__disabled__'),
    queryFn: () => fetchWarmupEvents(sessionId!),
    enabled: Boolean(sessionId),
    refetchInterval: 15_000,
  })
}

const EVENTS_PAGE_SIZE = 50

export function useWarmupEventsPaginated(sessionId: string | null) {
  const [pagination, setPagination] = useState({ sessionId, limit: EVENTS_PAGE_SIZE })
  const limit = pagination.sessionId === sessionId ? pagination.limit : EVENTS_PAGE_SIZE

  const query = useQuery<WarmupEventPage>({
    queryKey: [...warmupQueryKeys.events(sessionId ?? '__disabled__'), limit] as const,
    queryFn: () => fetchWarmupEvents(sessionId!, { limit }),
    enabled: Boolean(sessionId),
    refetchInterval: 15_000,
    placeholderData: keepPreviousData,
  })

  const total = query.data?.total ?? 0
  const events = query.data?.items ?? []
  const hasMore = events.length < total
  const isLoadingMore = query.isFetching && query.isPlaceholderData

  const loadMore = useCallback(() => {
    if (hasMore && !isLoadingMore) {
      setPagination({ sessionId, limit: limit + EVENTS_PAGE_SIZE })
    }
  }, [hasMore, isLoadingMore, limit, sessionId])

  return { events, total, hasMore, isLoadingMore, loadMore, isLoading: query.isLoading }
}

export function useWarmupLiveEvents(filters: WarmupLiveEventFilters = {}) {
  return useQuery<WarmupLiveEventPage>({
    queryKey: warmupQueryKeys.liveEvents(filters),
    queryFn: () => fetchWarmupLiveEvents(filters),
    refetchInterval: 30_000,
  })
}

export function useWarmupSessionDetail(sessionId: string | null) {
  return useQuery({
    queryKey: warmupQueryKeys.sessionDetail(sessionId ?? '__disabled__'),
    queryFn: () => fetchWarmupSessionDetail(sessionId!),
    enabled: Boolean(sessionId),
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status && ACTIVE_STATUSES.includes(status) ? 10_000 : false
    },
  })
}

export function useWarmupIsolationStatus(accountId: string | null | undefined) {
  return useQuery({
    queryKey: warmupQueryKeys.isolation(accountId ?? '__disabled__'),
    queryFn: () => fetchWarmupIsolationStatus(accountId!),
    enabled: Boolean(accountId),
    refetchInterval: 30_000,
    staleTime: 5_000,
  })
}

export function useWarmupValidate() {
  return useMutation({
    mutationFn: ({ accountId, strategyId }: { accountId: string; strategyId: string }) =>
      validateWarmup(accountId, strategyId),
  })
}

export function useApplyWarmupActionPreset() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ strategyId, preset }: { strategyId: string; preset: WarmupActionPreset }) =>
      applyWarmupActionPreset(strategyId, preset),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: warmupQueryKeys.strategies })
    },
  })
}

export function useCreateWarmupSession() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({
      accountId,
      cycleConfig,
      strategyId,
    }: {
      accountId: string
      strategyId: string
      cycleConfig?: { startHour: number; endHour: number; daysTotal: number; strategyPreset: WarmupPresetKind }
    }): Promise<WarmupSessionDetail> => {
      if (!cycleConfig) return createWarmupSession(accountId, strategyId)
      const response = await createCyclicWarmupSessions({
        account_ids: [accountId],
        start_hour: cycleConfig.startHour,
        end_hour: cycleConfig.endHour,
        days_total: cycleConfig.daysTotal,
        strategy_preset: cycleConfig.strategyPreset,
      })
      return response.items[0]
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: warmupQueryKeys.sessions })
    },
  })
}

export function usePauseWarmupSession() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ sessionId, reason }: { sessionId: string; reason: string }) => pauseWarmupSession(sessionId, reason),
    onSuccess: (_data, { sessionId }) => {
      void queryClient.invalidateQueries({ queryKey: warmupQueryKeys.sessions })
      void queryClient.invalidateQueries({ queryKey: warmupQueryKeys.sessionDetail(sessionId) })
      void queryClient.invalidateQueries({ queryKey: warmupQueryKeys.events(sessionId) })
    },
  })
}

export function useResumeWarmupSession() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ sessionId }: { sessionId: string }) => resumeWarmupSession(sessionId),
    onSuccess: (_data, { sessionId }) => {
      void queryClient.invalidateQueries({ queryKey: warmupQueryKeys.sessions })
      void queryClient.invalidateQueries({ queryKey: warmupQueryKeys.sessionDetail(sessionId) })
      void queryClient.invalidateQueries({ queryKey: warmupQueryKeys.events(sessionId) })
    },
  })
}

export function useUpdateWarmupDisabledActions() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ sessionId, actions }: { sessionId: string; actions: string[] }) =>
      updateWarmupDisabledActions(sessionId, actions),
    onSuccess: (_data, { sessionId }) => {
      void queryClient.invalidateQueries({ queryKey: warmupQueryKeys.sessions })
      void queryClient.invalidateQueries({ queryKey: warmupQueryKeys.sessionDetail(sessionId) })
      void queryClient.invalidateQueries({ queryKey: warmupQueryKeys.events(sessionId) })
    },
  })
}

export function useDeleteWarmupSession() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ sessionId }: { sessionId: string }) => deleteWarmupSession(sessionId),
    onSuccess: (_data, { sessionId }) => {
      void queryClient.invalidateQueries({ queryKey: warmupQueryKeys.sessions })
      void queryClient.removeQueries({ queryKey: warmupQueryKeys.sessionDetail(sessionId) })
      void queryClient.removeQueries({ queryKey: warmupQueryKeys.events(sessionId) })
    },
  })
}
