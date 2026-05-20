import { useQuery } from '@tanstack/react-query'
import { SectionCard, StatusCard } from '@stylisttg/ui'
import { dashboardApiClient } from '@/lib/apiClient'

type BehaviorProfile = {
  id: string
  account_id: string
  workspace_id: string
  typing_speed_baseline_cpm: number
  typo_rate_baseline: number
  profile_view_probability_baseline: number
  scroll_probability_baseline: number
  message_deletion_probability_baseline: number
  action_sequence_seed: number
  last_randomization_at: string | null
  created_at: string
  updated_at: string
}

type BehaviorProfileViewerProps = {
  accountId: string
  currentUserRole?: string
}

export function BehaviorProfileViewer({ accountId, currentUserRole }: BehaviorProfileViewerProps) {
  const isAdmin = currentUserRole === 'admin' || currentUserRole === 'owner'

  const profileQuery = useQuery({
    queryKey: ['behavior-profile', accountId],
    queryFn: async () => {
      return dashboardApiClient.request<BehaviorProfile>(
        `/api/accounts/${encodeURIComponent(accountId)}/behavior-profile`,
      )
    },
    enabled: isAdmin && !!accountId,
  })

  if (!isAdmin) return null

  const profile = profileQuery.data

  return (
    <SectionCard
      title="Behavior Profile"
      description="Per-account stable baseline parameters for human behavior emulation (admin only)."
    >
      {profileQuery.isPending ? (
        <div className="text-sm text-gray-500">Загрузка профиля поведения...</div>
      ) : profileQuery.isError ? (
        <div className="text-sm text-red-500">Не удалось загрузить профиль поведения.</div>
      ) : profile ? (
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          <StatusCard
            label="Typing Speed"
            value={`${profile.typing_speed_baseline_cpm} CPM`}
            detail="baseline chars/min"
            tone="neutral"
          />
          <StatusCard
            label="Typo Rate"
            value={`${(profile.typo_rate_baseline * 100).toFixed(1)}%`}
            detail="baseline probability"
            tone="neutral"
          />
          <StatusCard
            label="Profile View"
            value={`${(profile.profile_view_probability_baseline * 100).toFixed(0)}%`}
            detail="view probability"
            tone="neutral"
          />
          <StatusCard
            label="Scroll"
            value={`${(profile.scroll_probability_baseline * 100).toFixed(0)}%`}
            detail="scroll probability"
            tone="neutral"
          />
          <StatusCard
            label="Msg Deletion"
            value={`${(profile.message_deletion_probability_baseline * 100).toFixed(1)}%`}
            detail="deletion probability"
            tone="neutral"
          />
          <StatusCard
            label="Sequence Seed"
            value={`${profile.action_sequence_seed}`}
            detail="action shuffle seed"
            tone="neutral"
          />
        </div>
      ) : (
        <div className="text-sm text-gray-500">Нет данных.</div>
      )}
    </SectionCard>
  )
}
