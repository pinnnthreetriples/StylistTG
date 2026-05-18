export type {
  NeuroCampaign,
  NeuroCampaignAccount,
  NeuroCampaignAccountCreate,
  NeuroCampaignAccountPage,
  NeuroCampaignCreate,
  NeuroCampaignPage,
  NeuroCampaignUpdate,
  NeuroEvent,
  NeuroEventPage,
  NeuroGeneratedComment,
  NeuroGeneratedCommentPage,
  NeuroGeneratedCommentReject,
  NeuroGeneratedCommentUpdate,
  NeuroTarget,
  NeuroTargetCreate,
  NeuroTargetPage,
} from '@stylisttg/api-client'

export type CampaignMode = 'all_posts' | 'keyword_match' | 'random_posts' | 'semantic_match'
export type WorkMode = 'by_comment_count' | 'by_time_window' | 'manual' | 'scheduled'
export type ApprovalMode = 'manual_required' | 'trusted_auto' | 'auto'
export type SendMode = 'dry_run' | 'manual_approval' | 'semi_auto'
export type RotationStrategy = 'round_robin' | 'weighted' | 'least_used' | 'random'

export type CreateCampaignPayload = {
  name: string
  description?: string | null
}

export type UpdateCampaignPayload = {
  name?: string | null
  description?: string | null
  mode?: CampaignMode | null
  work_mode?: WorkMode | null
  approval_mode?: ApprovalMode | null
}
