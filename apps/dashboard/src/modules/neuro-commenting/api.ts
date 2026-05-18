import {
  addNeuroCampaignAccount,
  addNeuroCampaignTarget,
  approveNeuroGeneratedComment,
  createNeuroCampaign,
  deleteNeuroCampaignAccount,
  deleteNeuroCampaignTarget,
  editNeuroGeneratedComment,
  fetchNeuroCampaign,
  fetchNeuroCampaignAccounts,
  fetchNeuroCampaigns,
  fetchNeuroCampaignTargets,
  fetchNeuroEvents,
  fetchNeuroGeneratedComments,
  pauseNeuroCampaign,
  rejectNeuroGeneratedComment,
  startNeuroCampaign,
  stopNeuroCampaign,
  updateNeuroCampaign,
} from '@stylisttg/api-client'

import { dashboardApiClient } from '@/modules/shared'

import type {
  NeuroCampaignAccountCreate,
  NeuroCampaignCreate,
  NeuroCampaignUpdate,
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

export function editGeneratedComment(commentId: string, payload: NeuroGeneratedCommentUpdate) {
  return editNeuroGeneratedComment(client, commentId, payload)
}

export function approveGeneratedComment(commentId: string) {
  return approveNeuroGeneratedComment(client, commentId)
}

export function rejectGeneratedComment(commentId: string, payload: NeuroGeneratedCommentReject) {
  return rejectNeuroGeneratedComment(client, commentId, payload)
}

export function listEvents(params?: { campaign_id?: string; page?: number; limit?: number }) {
  return fetchNeuroEvents(client, params)
}
