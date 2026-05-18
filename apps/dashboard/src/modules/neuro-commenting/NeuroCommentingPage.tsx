import { PageHeader, PageShell } from '@stylisttg/ui'
import { useState } from 'react'

import { AccountsSection } from './components/AccountsSection'
import { CampaignDetailSection } from './components/CampaignDetailSection'
import { CampaignListSection } from './components/CampaignListSection'
import { EventsSection } from './components/EventsSection'
import { GeneratedCommentsSection } from './components/GeneratedCommentsSection'
import { TargetsSection } from './components/TargetsSection'

export function NeuroCommentingPage({ initialSelectedCampaignId = null }: { initialSelectedCampaignId?: string | null } = {}) {
  const [selectedCampaignId, setSelectedCampaignId] = useState<string | null>(initialSelectedCampaignId)

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
              <div className="grid gap-4 sm:grid-cols-2">
                <AccountsSection campaignId={selectedCampaignId} />
                <TargetsSection campaignId={selectedCampaignId} />
              </div>
              <GeneratedCommentsSection campaignId={selectedCampaignId} />
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
