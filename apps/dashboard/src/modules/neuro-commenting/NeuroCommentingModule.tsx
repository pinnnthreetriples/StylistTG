import { PageHeader, ProductEmptyState } from '@stylisttg/ui'
import { useState } from 'react'

import {
  useCreateNeuroChannelRule,
  useDeleteNeuroChannelRule,
  useNeuroAccountStats,
  useNeuroCampaignAttempts,
  useNeuroCampaignStats,
  useNeuroChannelRules,
  useNeuroChannelStats,
} from './hooks'
import { AnalyticsSection } from './components/AnalyticsSection'
import { AttemptsSection } from './components/AttemptsSection'
import { ChannelRulesSection } from './components/ChannelRulesSection'

type NeuroCommentingModuleProps = {
  campaignId?: string
}

export function NeuroCommentingModule({ campaignId }: NeuroCommentingModuleProps) {
  const [draftCampaignId, setDraftCampaignId] = useState(campaignId ?? '')
  const [activeCampaignId, setActiveCampaignId] = useState(campaignId ?? '')
  const hasCampaign = activeCampaignId.trim().length > 0
  const queryCampaignId = hasCampaign ? activeCampaignId : null

  const campaignStats = useNeuroCampaignStats(queryCampaignId)
  const accountStats = useNeuroAccountStats(queryCampaignId)
  const channelStats = useNeuroChannelStats(queryCampaignId)
  const attempts = useNeuroCampaignAttempts(queryCampaignId)
  const rules = useNeuroChannelRules()
  const createRule = useCreateNeuroChannelRule()
  const deleteRule = useDeleteNeuroChannelRule()

  return (
    <div className="mx-auto grid max-w-6xl gap-5 px-5 py-6">
      <PageHeader
        eyebrow="Модули"
        title="NeuroCommenting"
        description="Ручной контроль кампаний, лимитов, попыток, правил каналов и метрик без auto-send."
      />
      <form
        className="flex flex-wrap items-end gap-3"
        onSubmit={(event) => {
          event.preventDefault()
          setActiveCampaignId(draftCampaignId.trim())
        }}
      >
        <label className="grid gap-1 text-sm">
          Campaign ID
          <input
            className="h-9 min-w-80 rounded-md border px-3"
            value={draftCampaignId}
            onChange={(event) => setDraftCampaignId(event.target.value)}
          />
        </label>
        <button className="h-9 rounded-md border px-3" type="submit">
          Load
        </button>
      </form>
      {!hasCampaign ? (
        <ProductEmptyState
          title="Выберите кампанию"
          description="Введите campaign_id, чтобы открыть аналитику, историю попыток и правила каналов."
        />
      ) : (
        <>
          <AnalyticsSection
            stats={campaignStats.data ?? null}
            accounts={accountStats.data?.items ?? []}
            channels={channelStats.data?.items ?? []}
            loading={campaignStats.isLoading || accountStats.isLoading || channelStats.isLoading}
            error={
              campaignStats.isError || accountStats.isError || channelStats.isError
                ? 'Не удалось загрузить аналитику'
                : null
            }
          />
          <AttemptsSection
            attempts={attempts.data?.items ?? []}
            loading={attempts.isLoading}
            error={attempts.isError ? 'Не удалось загрузить попытки' : null}
          />
        </>
      )}
      <ChannelRulesSection
        rules={rules.data?.items ?? []}
        loading={rules.isLoading}
        error={rules.isError ? 'Не удалось загрузить правила каналов' : null}
        onCreate={(payload) => {
          createRule.mutate(payload)
        }}
        onDelete={(ruleId) => {
          deleteRule.mutate(ruleId)
        }}
      />
    </div>
  )
}
