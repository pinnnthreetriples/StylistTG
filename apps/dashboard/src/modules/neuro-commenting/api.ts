import {
  addNeuroCampaignAccount,
  addNeuroCampaignTarget,
  approveNeuroGeneratedComment,
  blacklistNeuroTarget as blacklistTypedNeuroTarget,
  createNeuroCampaign,
  createNeuroChannelRule as createTypedNeuroChannelRule,
  deleteNeuroCampaignAccount,
  deleteNeuroCampaignTarget,
  deleteNeuroChannelRule as deleteTypedNeuroChannelRule,
  editNeuroGeneratedComment,
  fetchNeuroAccountStats as fetchTypedNeuroAccountStats,
  fetchNeuroCampaign,
  fetchNeuroCampaignAccounts,
  fetchNeuroCampaignAttempts as fetchTypedNeuroCampaignAttempts,
  fetchNeuroCampaigns,
  fetchNeuroCampaignStats as fetchTypedNeuroCampaignStats,
  fetchNeuroCampaignTargets,
  fetchNeuroChannelRules as fetchTypedNeuroChannelRules,
  fetchNeuroChannelStats as fetchTypedNeuroChannelStats,
  fetchNeuroEvents,
  fetchNeuroFailureReasons as fetchTypedNeuroFailureReasons,
  fetchNeuroGeneratedComments,
  fetchNeuroLiveReadiness as fetchTypedNeuroLiveReadiness,
  fetchNeuroAttempts,
  fetchNeuroObservedPosts,
  fetchNeuroPromptPresets as fetchTypedNeuroPromptPresets,
  generateNeuroObservedPost,
  observeNeuroCampaign,
  observeNeuroTarget,
  pauseNeuroCampaign,
  pauseNeuroTarget as pauseTypedNeuroTarget,
  rejectNeuroGeneratedComment,
  refreshNeuroTargetMetadata,
  resumeNeuroTarget as resumeTypedNeuroTarget,
  resolveNeuroObservedPostDiscussion as resolveTypedNeuroObservedPostDiscussion,
  sendNeuroGeneratedComment,
  startNeuroCampaign,
  stopNeuroCampaign,
  updateNeuroCampaign,
  whitelistNeuroTarget as whitelistTypedNeuroTarget,
} from '@stylisttg/api-client'

import { dashboardApiClient } from '@/modules/shared'

import type {
  NeuroCampaignAccountCreate,
  NeuroCampaignCreate,
  NeuroCampaignUpdate,
  NeuroChannelRuleCreate,
  NeuroGeneratedCommentReject,
  NeuroGeneratedCommentUpdate,
  NeuroTargetCreate,
} from './types'

const client = dashboardApiClient

export function listCampaigns(params?: { page?: number; limit?: number }) {
  return fetchNeuroCampaigns(client, params)
}

export function createCampaign(payload: NeuroCampaignCreate) {
  return createNeuroCampaign(client, payload)
}

export function getCampaign(campaignId: string) {
  return fetchNeuroCampaign(client, campaignId)
}

export function updateCampaign(campaignId: string, payload: NeuroCampaignUpdate) {
  return updateNeuroCampaign(client, campaignId, payload)
}

export function startCampaign(campaignId: string) {
  return startNeuroCampaign(client, campaignId)
}

export function pauseCampaign(campaignId: string) {
  return pauseNeuroCampaign(client, campaignId)
}

export function stopCampaign(campaignId: string) {
  return stopNeuroCampaign(client, campaignId)
}

export function fetchNeuroLiveReadiness(campaignId: string) {
  return fetchTypedNeuroLiveReadiness(client, campaignId)
}

export function listCampaignAccounts(campaignId: string, params?: { page?: number; limit?: number }) {
  return fetchNeuroCampaignAccounts(client, campaignId, params)
}

export function addCampaignAccount(campaignId: string, payload: NeuroCampaignAccountCreate) {
  return addNeuroCampaignAccount(client, campaignId, payload)
}

export function removeCampaignAccount(campaignId: string, accountId: string) {
  return deleteNeuroCampaignAccount(client, campaignId, accountId)
}

export function listCampaignTargets(campaignId: string, params?: { page?: number; limit?: number }) {
  return fetchNeuroCampaignTargets(client, campaignId, params)
}

export function addCampaignTarget(campaignId: string, payload: NeuroTargetCreate) {
  return addNeuroCampaignTarget(client, campaignId, payload)
}

export function removeCampaignTarget(campaignId: string, targetId: string) {
  return deleteNeuroCampaignTarget(client, campaignId, targetId)
}

export function listGeneratedComments(params?: { campaign_id?: string; page?: number; limit?: number }) {
  return fetchNeuroGeneratedComments(client, params)
}

export function listObservedPosts(params?: { campaign_id?: string; target_id?: string; page?: number; limit?: number }) {
  return fetchNeuroObservedPosts(client, params)
}

export function observeCampaign(campaignId: string, payload?: { limit?: number | null; generate?: boolean }) {
  return observeNeuroCampaign(client, campaignId, { generate: payload?.generate ?? true, limit: payload?.limit ?? undefined })
}

export function observeTarget(
  campaignId: string,
  targetId: string,
  payload?: { limit?: number | null; generate?: boolean },
) {
  return observeNeuroTarget(client, campaignId, targetId, { generate: payload?.generate ?? true, limit: payload?.limit ?? undefined })
}

export function refreshTargetMetadata(campaignId: string, targetId: string) {
  return refreshNeuroTargetMetadata(client, campaignId, targetId)
}

export function generateObservedPost(observedPostId: string, payload?: { force?: boolean }) {
  return generateNeuroObservedPost(client, observedPostId, { force: payload?.force ?? false })
}

export function resolveObservedPostDiscussion(observedPostId: string) {
  return resolveTypedNeuroObservedPostDiscussion(client, observedPostId)
}

export function editGeneratedComment(commentId: string, payload: NeuroGeneratedCommentUpdate) {
  return editNeuroGeneratedComment(client, commentId, payload)
}

export function approveGeneratedComment(commentId: string) {
  return approveNeuroGeneratedComment(client, commentId)
}

export function rejectGeneratedComment(commentId: string, payload: NeuroGeneratedCommentReject) {
  return rejectNeuroGeneratedComment(client, commentId, payload)
}

export function sendGeneratedComment(commentId: string, payload?: { enqueue?: boolean }) {
  return sendNeuroGeneratedComment(client, commentId, { enqueue: payload?.enqueue ?? true })
}

export function listAttempts(params?: { campaign_id?: string; generated_comment_id?: string; page?: number; limit?: number }) {
  return fetchNeuroAttempts(client, params)
}

export function listEvents(params?: { campaign_id?: string; page?: number; limit?: number }) {
  return fetchNeuroEvents(client, params)
}

export function fetchNeuroCampaignStats(campaignId: string) {
  return fetchTypedNeuroCampaignStats(client, campaignId)
}

export function fetchNeuroAccountStats(campaignId: string) {
  return fetchTypedNeuroAccountStats(client, campaignId)
}

export function fetchNeuroChannelStats(campaignId: string) {
  return fetchTypedNeuroChannelStats(client, campaignId)
}

export function fetchNeuroCampaignAttempts(campaignId: string) {
  return fetchTypedNeuroCampaignAttempts(client, campaignId)
}

export function fetchNeuroFailureReasons(campaignId: string) {
  return fetchTypedNeuroFailureReasons(client, campaignId)
}

export function fetchNeuroChannelRules() {
  return fetchTypedNeuroChannelRules(client)
}

export function fetchNeuroPromptPresets() {
  return fetchTypedNeuroPromptPresets(client)
}

export function createNeuroChannelRule(payload: NeuroChannelRuleCreate) {
  return createTypedNeuroChannelRule(client, payload)
}

export function deleteNeuroChannelRule(ruleId: string) {
  return deleteTypedNeuroChannelRule(client, ruleId)
}

export function blacklistNeuroTarget(targetId: string) {
  return blacklistTypedNeuroTarget(client, targetId)
}

export function whitelistNeuroTarget(targetId: string) {
  return whitelistTypedNeuroTarget(client, targetId)
}

export function pauseNeuroTarget(targetId: string) {
  return pauseTypedNeuroTarget(client, targetId)
}

export function resumeNeuroTarget(targetId: string) {
  return resumeTypedNeuroTarget(client, targetId)
}
