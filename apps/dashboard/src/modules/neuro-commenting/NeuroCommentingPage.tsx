import { PageHeader, PageShell } from '@stylisttg/ui'
import { useState } from 'react'

import { AccountsSection } from './components/AccountsSection'
import { AnalyticsSection } from './components/AnalyticsSection'
import { AttemptsSection } from './components/AttemptsSection'
import { CampaignDetailSection } from './components/CampaignDetailSection'
import { CampaignListSection } from './components/CampaignListSection'
import { ChannelRulesSection } from './components/ChannelRulesSection'
import { EventsSection } from './components/EventsSection'
import { GeneratedCommentsSection } from './components/GeneratedCommentsSection'
import { LiveReadinessSection } from './components/LiveReadinessSection'
import { TargetsSection } from './components/TargetsSection'
import {
  useCreateNeuroChannelRule,
  useDeleteNeuroChannelRule,
  useNeuroAccountStats,
  useNeuroCampaignStats,
  useNeuroChannelRules,
  useNeuroChannelStats,
} from './hooks'

export function NeuroCommentingPage({ initialSelectedCampaignId = null }: { initialSelectedCampaignId?: string | null } = {}) {
  const [selectedCampaignId, setSelectedCampaignId] = useState<string | null>(initialSelectedCampaignId)
  const campaignStats = useNeuroCampaignStats(selectedCampaignId)
  const accountStats = useNeuroAccountStats(selectedCampaignId)
  const channelStats = useNeuroChannelStats(selectedCampaignId)
  const channelRules = useNeuroChannelRules()
  const createRule = useCreateNeuroChannelRule()
  const deleteRule = useDeleteNeuroChannelRule()
  const analyticsError =
    campaignStats.isError || accountStats.isError || channelStats.isError ? 'Не удалось загрузить аналитику' : null

  return (
    <PageShell>
      <PageHeader
        title="Нейро-комментирование"
        description="Управление кампаниями автоматического комментирования"
      />

      <div className="mt-6 grid gap-6 lg:grid-cols-[320px_1fr]">
        <aside>
          <CampaignListSection selectedId={selectedCampaignId} onSelect={setSelectedCampaignId} />
        </aside>

        <div className="space-y-4">
          {selectedCampaignId ? (
            <>
              <CampaignDetailSection campaignId={selectedCampaignId} />
              <LiveReadinessSection campaignId={selectedCampaignId} />
              <div className="grid gap-4 sm:grid-cols-2">
                <AccountsSection campaignId={selectedCampaignId} />
                <TargetsSection campaignId={selectedCampaignId} />
              </div>
              <GeneratedCommentsSection campaignId={selectedCampaignId} />
              <AnalyticsSection
                stats={campaignStats.data ?? null}
                accounts={accountStats.data?.items ?? []}
                channels={channelStats.data?.items ?? []}
                loading={campaignStats.isLoading || accountStats.isLoading || channelStats.isLoading}
                error={analyticsError}
              />
              <AttemptsSection campaignId={selectedCampaignId} />
              <ChannelRulesSection
                rules={channelRules.data?.items ?? []}
                loading={channelRules.isLoading}
                error={
                  channelRules.isError || createRule.isError || deleteRule.isError
                    ? 'Не удалось сохранить правила каналов'
                    : null
                }
                onCreate={(payload) => createRule.mutate(payload)}
                onDelete={(ruleId) => deleteRule.mutate(ruleId)}
              />
              <EventsSection campaignId={selectedCampaignId} />
            </>
          ) : (
            <div className="flex items-center justify-center rounded-lg border border-dashed border-gray-200 bg-gray-50 p-12 text-sm text-gray-500">
              Выберите кампанию или создайте новую
            </div>
          )}
        </div>
      </div>
    </PageShell>
  )
}
