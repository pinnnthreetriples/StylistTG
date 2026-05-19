import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  addCampaignAccount,
  addCampaignTarget,
  approveGeneratedComment,
  createCampaign,
  editGeneratedComment,
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
  rejectGeneratedComment,
  refreshTargetMetadata,
  removeCampaignAccount,
  removeCampaignTarget,
  sendGeneratedComment,
  startCampaign,
  stopCampaign,
  updateCampaign,
} from './api'
import type {
  CreateCampaignPayload,
  NeuroCampaignAccountCreate,
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

export function useGeneratedCommentMutations(campaignId?: string) {
  const queryClient = useQueryClient()
  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: neuroQueryKeys.generatedComments(campaignId) })
    void queryClient.invalidateQueries({ queryKey: neuroQueryKeys.attempts(campaignId) })
    void queryClient.invalidateQueries({ queryKey: neuroQueryKeys.events(campaignId) })
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
