import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  addCampaignAccount,
  addCampaignTarget,
  approveGeneratedComment,
  blacklistNeuroTarget,
  createCampaign,
  createNeuroChannelRule,
  deleteNeuroChannelRule,
  editGeneratedComment,
  fetchNeuroAccountStats,
  fetchNeuroCampaignAttempts,
  fetchNeuroCampaignStats,
  fetchNeuroChannelRules,
  fetchNeuroChannelStats,
  fetchNeuroFailureReasons,
  fetchNeuroLiveReadiness,
  getCampaign,
  listCampaignAccounts,
  listCampaigns,
  listCampaignTargets,
  listAttempts,
  listEvents,
  listGeneratedComments,
  listObservedPosts,
  observeCampaign,
  observeTarget,
  pauseCampaign,
  pauseNeuroTarget,
  rejectGeneratedComment,
  refreshTargetMetadata,
  removeCampaignAccount,
  removeCampaignTarget,
  resumeNeuroTarget,
  resolveObservedPostDiscussion,
  sendGeneratedComment,
  startCampaign,
  stopCampaign,
  updateCampaign,
  whitelistNeuroTarget,
} from './api'
import type {
  CreateCampaignPayload,
  NeuroCampaignAccountCreate,
  NeuroChannelRuleCreate,
  NeuroGeneratedCommentReject,
  NeuroGeneratedCommentUpdate,
  NeuroTargetCreate,
  UpdateCampaignPayload,
} from './types'

export const neuroQueryKeys = {
  campaigns: ['neuro-commenting', 'campaigns'] as const,
  campaign: (campaignId: string) => ['neuro-commenting', 'campaigns', campaignId] as const,
  accounts: (campaignId: string) => ['neuro-commenting', 'campaigns', campaignId, 'accounts'] as const,
  targets: (campaignId: string) => ['neuro-commenting', 'campaigns', campaignId, 'targets'] as const,
  observedPosts: (campaignId?: string) => ['neuro-commenting', 'observed-posts', campaignId ?? 'all'] as const,
  generatedComments: (campaignId?: string) => ['neuro-commenting', 'generated-comments', campaignId ?? 'all'] as const,
  attempts: (campaignId?: string) => ['neuro-commenting', 'attempts', campaignId ?? 'all'] as const,
  events: (campaignId?: string) => ['neuro-commenting', 'events', campaignId ?? 'all'] as const,
  campaignStats: (campaignId: string) => ['neuro-commenting', 'campaigns', campaignId, 'stats'] as const,
  liveReadiness: (campaignId: string) => ['neuro-commenting', 'campaigns', campaignId, 'live-readiness'] as const,
  accountStats: (campaignId: string) => ['neuro-commenting', 'campaigns', campaignId, 'account-stats'] as const,
  channelStats: (campaignId: string) => ['neuro-commenting', 'campaigns', campaignId, 'channel-stats'] as const,
  campaignAttempts: (campaignId: string) => ['neuro-commenting', 'campaigns', campaignId, 'attempts'] as const,
  failureReasons: (campaignId: string) => ['neuro-commenting', 'campaigns', campaignId, 'failure-reasons'] as const,
  channelRules: ['neuro-commenting', 'channel-rules'] as const,
}

export function useNeuroCampaigns() {
  return useQuery({
    queryKey: neuroQueryKeys.campaigns,
    queryFn: () => listCampaigns(),
    placeholderData: keepPreviousData,
  })
}

export function useNeuroCampaign(campaignId: string | null) {
  return useQuery({
    queryKey: neuroQueryKeys.campaign(campaignId ?? '__disabled__'),
    queryFn: () => getCampaign(campaignId!),
    enabled: Boolean(campaignId),
  })
}

export function useNeuroCampaignAccounts(campaignId: string | null) {
  return useQuery({
    queryKey: neuroQueryKeys.accounts(campaignId ?? '__disabled__'),
    queryFn: () => listCampaignAccounts(campaignId!),
    enabled: Boolean(campaignId),
  })
}

export function useNeuroCampaignTargets(campaignId: string | null) {
  return useQuery({
    queryKey: neuroQueryKeys.targets(campaignId ?? '__disabled__'),
    queryFn: () => listCampaignTargets(campaignId!),
    enabled: Boolean(campaignId),
  })
}

export function useNeuroGeneratedComments(campaignId?: string) {
  return useQuery({
    queryKey: neuroQueryKeys.generatedComments(campaignId),
    queryFn: () => listGeneratedComments(campaignId ? { campaign_id: campaignId } : undefined),
    refetchInterval: 20_000,
  })
}

export function useNeuroObservedPosts(campaignId?: string) {
  return useQuery({
    queryKey: neuroQueryKeys.observedPosts(campaignId),
    queryFn: () => listObservedPosts(campaignId ? { campaign_id: campaignId } : undefined),
    refetchInterval: 20_000,
  })
}

export function useNeuroAttempts(campaignId?: string) {
  return useQuery({
    queryKey: neuroQueryKeys.attempts(campaignId),
    queryFn: () => listAttempts(campaignId ? { campaign_id: campaignId } : undefined),
    refetchInterval: 20_000,
  })
}

export function useNeuroCampaignStats(campaignId: string | null) {
  return useQuery({
    queryKey: neuroQueryKeys.campaignStats(campaignId ?? '__disabled__'),
    queryFn: () => fetchNeuroCampaignStats(campaignId!),
    enabled: Boolean(campaignId),
  })
}

export function useNeuroLiveReadiness(campaignId: string | null) {
  return useQuery({
    queryKey: neuroQueryKeys.liveReadiness(campaignId ?? '__disabled__'),
    queryFn: () => fetchNeuroLiveReadiness(campaignId!),
    enabled: Boolean(campaignId),
  })
}

export function useNeuroAccountStats(campaignId: string | null) {
  return useQuery({
    queryKey: neuroQueryKeys.accountStats(campaignId ?? '__disabled__'),
    queryFn: () => fetchNeuroAccountStats(campaignId!),
    enabled: Boolean(campaignId),
  })
}

export function useNeuroChannelStats(campaignId: string | null) {
  return useQuery({
    queryKey: neuroQueryKeys.channelStats(campaignId ?? '__disabled__'),
    queryFn: () => fetchNeuroChannelStats(campaignId!),
    enabled: Boolean(campaignId),
  })
}

export function useNeuroCampaignAttempts(campaignId: string | null) {
  return useQuery({
    queryKey: neuroQueryKeys.campaignAttempts(campaignId ?? '__disabled__'),
    queryFn: () => fetchNeuroCampaignAttempts(campaignId!),
    enabled: Boolean(campaignId),
  })
}

export function useNeuroFailureReasons(campaignId: string | null) {
  return useQuery({
    queryKey: neuroQueryKeys.failureReasons(campaignId ?? '__disabled__'),
    queryFn: () => fetchNeuroFailureReasons(campaignId!),
    enabled: Boolean(campaignId),
  })
}

export function useNeuroChannelRules() {
  return useQuery({
    queryKey: neuroQueryKeys.channelRules,
    queryFn: () => fetchNeuroChannelRules(),
  })
}

export function useNeuroEvents(campaignId?: string) {
  return useQuery({
    queryKey: neuroQueryKeys.events(campaignId),
    queryFn: () => listEvents(campaignId ? { campaign_id: campaignId } : undefined),
    refetchInterval: 20_000,
  })
}

export function useObserveCampaignMutation(campaignId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => observeCampaign(campaignId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: neuroQueryKeys.observedPosts(campaignId) })
      void queryClient.invalidateQueries({ queryKey: neuroQueryKeys.generatedComments(campaignId) })
      void queryClient.invalidateQueries({ queryKey: neuroQueryKeys.events(campaignId) })
      void queryClient.invalidateQueries({ queryKey: neuroQueryKeys.liveReadiness(campaignId) })
    },
  })
}

export function useCreateNeuroCampaign() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: CreateCampaignPayload) => createCampaign(payload as Parameters<typeof createCampaign>[0]),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: neuroQueryKeys.campaigns }),
  })
}

export function useUpdateNeuroCampaign(campaignId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: UpdateCampaignPayload) => updateCampaign(campaignId, payload as Parameters<typeof updateCampaign>[1]),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: neuroQueryKeys.campaigns })
      void queryClient.invalidateQueries({ queryKey: neuroQueryKeys.campaign(campaignId) })
      void queryClient.invalidateQueries({ queryKey: neuroQueryKeys.events(campaignId) })
      void queryClient.invalidateQueries({ queryKey: neuroQueryKeys.liveReadiness(campaignId) })
    },
  })
}

export function useCampaignLifecycleMutation(campaignId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (action: 'start' | 'pause' | 'stop') => {
      if (action === 'start') return startCampaign(campaignId)
      if (action === 'pause') return pauseCampaign(campaignId)
      return stopCampaign(campaignId)
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: neuroQueryKeys.campaigns })
      void queryClient.invalidateQueries({ queryKey: neuroQueryKeys.campaign(campaignId) })
      void queryClient.invalidateQueries({ queryKey: neuroQueryKeys.events(campaignId) })
      void queryClient.invalidateQueries({ queryKey: neuroQueryKeys.liveReadiness(campaignId) })
    },
  })
}

export function useAddCampaignAccount(campaignId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: NeuroCampaignAccountCreate) => addCampaignAccount(campaignId, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: neuroQueryKeys.accounts(campaignId) })
      void queryClient.invalidateQueries({ queryKey: neuroQueryKeys.events(campaignId) })
      void queryClient.invalidateQueries({ queryKey: neuroQueryKeys.liveReadiness(campaignId) })
    },
  })
}

export function useRemoveCampaignAccount(campaignId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (accountId: string) => removeCampaignAccount(campaignId, accountId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: neuroQueryKeys.accounts(campaignId) })
      void queryClient.invalidateQueries({ queryKey: neuroQueryKeys.events(campaignId) })
      void queryClient.invalidateQueries({ queryKey: neuroQueryKeys.liveReadiness(campaignId) })
    },
  })
}

export function useAddCampaignTarget(campaignId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: NeuroTargetCreate) => addCampaignTarget(campaignId, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: neuroQueryKeys.targets(campaignId) })
      void queryClient.invalidateQueries({ queryKey: neuroQueryKeys.events(campaignId) })
      void queryClient.invalidateQueries({ queryKey: neuroQueryKeys.liveReadiness(campaignId) })
    },
  })
}

export function useRemoveCampaignTarget(campaignId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (targetId: string) => removeCampaignTarget(campaignId, targetId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: neuroQueryKeys.targets(campaignId) })
      void queryClient.invalidateQueries({ queryKey: neuroQueryKeys.events(campaignId) })
      void queryClient.invalidateQueries({ queryKey: neuroQueryKeys.liveReadiness(campaignId) })
    },
  })
}

export function useTargetRuntimeMutations(campaignId: string) {
  const queryClient = useQueryClient()
  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: neuroQueryKeys.targets(campaignId) })
    void queryClient.invalidateQueries({ queryKey: neuroQueryKeys.observedPosts(campaignId) })
    void queryClient.invalidateQueries({ queryKey: neuroQueryKeys.generatedComments(campaignId) })
    void queryClient.invalidateQueries({ queryKey: neuroQueryKeys.events(campaignId) })
    void queryClient.invalidateQueries({ queryKey: neuroQueryKeys.liveReadiness(campaignId) })
  }
  return {
    observe: useMutation({
      mutationFn: (targetId: string) => observeTarget(campaignId, targetId),
      onSuccess: invalidate,
    }),
    refreshMetadata: useMutation({
      mutationFn: (targetId: string) => refreshTargetMetadata(campaignId, targetId),
      onSuccess: invalidate,
    }),
  }
}

export function useCreateNeuroChannelRule() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: NeuroChannelRuleCreate) => createNeuroChannelRule(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: neuroQueryKeys.channelRules })
    },
  })
}

export function useDeleteNeuroChannelRule() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (ruleId: string) => deleteNeuroChannelRule(ruleId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: neuroQueryKeys.channelRules })
    },
  })
}

export function useTargetRuleActions(campaignId: string) {
  const queryClient = useQueryClient()
  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: neuroQueryKeys.targets(campaignId) })
    void queryClient.invalidateQueries({ queryKey: neuroQueryKeys.channelRules })
    void queryClient.invalidateQueries({ queryKey: neuroQueryKeys.channelStats(campaignId) })
    void queryClient.invalidateQueries({ queryKey: neuroQueryKeys.events(campaignId) })
    void queryClient.invalidateQueries({ queryKey: neuroQueryKeys.liveReadiness(campaignId) })
  }
  return {
    pause: useMutation({ mutationFn: (targetId: string) => pauseNeuroTarget(targetId), onSuccess: invalidate }),
    resume: useMutation({ mutationFn: (targetId: string) => resumeNeuroTarget(targetId), onSuccess: invalidate }),
    blacklist: useMutation({ mutationFn: (targetId: string) => blacklistNeuroTarget(targetId), onSuccess: invalidate }),
    whitelist: useMutation({ mutationFn: (targetId: string) => whitelistNeuroTarget(targetId), onSuccess: invalidate }),
  }
}

export function useGeneratedCommentMutations(campaignId?: string) {
  const queryClient = useQueryClient()
  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: neuroQueryKeys.generatedComments(campaignId) })
    void queryClient.invalidateQueries({ queryKey: neuroQueryKeys.attempts(campaignId) })
    void queryClient.invalidateQueries({ queryKey: neuroQueryKeys.events(campaignId) })
    if (campaignId) {
      void queryClient.invalidateQueries({ queryKey: neuroQueryKeys.liveReadiness(campaignId) })
    }
  }
  return {
    edit: useMutation({
      mutationFn: ({ commentId, payload }: { commentId: string; payload: NeuroGeneratedCommentUpdate }) =>
        editGeneratedComment(commentId, payload),
      onSuccess: invalidate,
    }),
    approve: useMutation({
      mutationFn: (commentId: string) => approveGeneratedComment(commentId),
      onSuccess: invalidate,
    }),
    reject: useMutation({
      mutationFn: ({ commentId, payload }: { commentId: string; payload: NeuroGeneratedCommentReject }) =>
        rejectGeneratedComment(commentId, payload),
      onSuccess: invalidate,
    }),
    send: useMutation({
      mutationFn: (commentId: string) => sendGeneratedComment(commentId),
      onSuccess: invalidate,
    }),
  }
}

export function useResolveObservedPostDiscussionMutation(campaignId?: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (observedPostId: string) => resolveObservedPostDiscussion(observedPostId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: neuroQueryKeys.observedPosts(campaignId) })
      void queryClient.invalidateQueries({ queryKey: neuroQueryKeys.generatedComments(campaignId) })
      void queryClient.invalidateQueries({ queryKey: neuroQueryKeys.events(campaignId) })
      if (campaignId) {
        void queryClient.invalidateQueries({ queryKey: neuroQueryKeys.liveReadiness(campaignId) })
      }
    },
  })
}
