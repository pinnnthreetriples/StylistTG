import { Button, PageHeader, PageShell } from '@stylisttg/ui'
import { Plus } from 'lucide-react'
import { useState } from 'react'

import { AccountsSection } from './components/AccountsSection'
import { AnalyticsSection } from './components/AnalyticsSection'
import { ApprovalInbox } from './components/ApprovalInbox'
import { AttemptsSection } from './components/AttemptsSection'
import { CampaignDetailSection } from './components/CampaignDetailSection'
import { CampaignListSection } from './components/CampaignListSection'
import { CampaignWizard } from './components/CampaignWizard'
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

export type NeuroCommentingTab = 'setup' | 'queue' | 'analytics'

const TAB_LABELS: Record<NeuroCommentingTab, string> = {
  setup: 'Настройка',
  queue: 'Очередь модерации',
  analytics: 'Аналитика',
}

export function NeuroCommentingPage({
  initialSelectedCampaignId = null,
  initialTab = 'setup',
}: {
  initialSelectedCampaignId?: string | null
  initialTab?: NeuroCommentingTab
} = {}) {
  const [selectedCampaignId, setSelectedCampaignId] = useState<string | null>(initialSelectedCampaignId)
  const [tab, setTab] = useState<NeuroCommentingTab>(initialTab)
  const [showWizard, setShowWizard] = useState(false)
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
        <aside className="space-y-3">
          <Button
            size="sm"
            variant="outline"
            icon={<Plus className="size-3.5" />}
            onClick={() => setShowWizard(true)}
          >
            Новая кампания (визард)
          </Button>
          <CampaignListSection selectedId={selectedCampaignId} onSelect={setSelectedCampaignId} />
        </aside>

        <div className="space-y-4">
          {showWizard ? (
            <CampaignWizard
              onCreated={(campaignId) => {
                setSelectedCampaignId(campaignId)
                setShowWizard(false)
                setTab('setup')
              }}
              onCancel={() => setShowWizard(false)}
            />
          ) : null}

          {selectedCampaignId ? (
            <>
              <NeuroCommentingTabs tab={tab} onChange={setTab} />
              {tab === 'setup' ? (
                <>
                  <CampaignDetailSection campaignId={selectedCampaignId} />
                  <LiveReadinessSection campaignId={selectedCampaignId} />
                  <div className="grid gap-4 sm:grid-cols-2">
                    <AccountsSection campaignId={selectedCampaignId} />
                    <TargetsSection campaignId={selectedCampaignId} />
                  </div>
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
                </>
              ) : null}
              {tab === 'queue' ? (
                <>
                  <ApprovalInbox campaignId={selectedCampaignId} />
                  <GeneratedCommentsSection campaignId={selectedCampaignId} />
                </>
              ) : null}
              {tab === 'analytics' ? (
                <>
                  <AnalyticsSection
                    stats={campaignStats.data ?? null}
                    accounts={accountStats.data?.items ?? []}
                    channels={channelStats.data?.items ?? []}
                    loading={campaignStats.isLoading || accountStats.isLoading || channelStats.isLoading}
                    error={analyticsError}
                  />
                  <AttemptsSection campaignId={selectedCampaignId} />
                  <EventsSection campaignId={selectedCampaignId} />
                </>
              ) : null}
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

function NeuroCommentingTabs({
  tab,
  onChange,
}: {
  tab: NeuroCommentingTab
  onChange: (next: NeuroCommentingTab) => void
}) {
  const order: NeuroCommentingTab[] = ['setup', 'queue', 'analytics']
  return (
    <nav className="flex flex-wrap gap-1 rounded-lg border border-gray-200 bg-white p-1 text-sm">
      {order.map((value) => {
        const active = value === tab
        return (
          <button
            key={value}
            type="button"
            role="tab"
            aria-selected={active}
            data-testid={`neuro-commenting-tab-${value}`}
            className={`rounded-md px-3 py-1.5 transition ${
              active
                ? 'bg-navy-50 font-medium text-navy-900'
                : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
            }`}
            onClick={() => onChange(value)}
          >
            {TAB_LABELS[value]}
          </button>
        )
      })}
    </nav>
  )
}
