import { Button, Card, Skeleton } from '@stylisttg/ui'
import { Pause, Play, Square } from 'lucide-react'

import { useCampaignLifecycleMutation, useNeuroCampaign } from '../hooks'

import { CampaignStatusBadge } from './CampaignStatusBadge'

export function CampaignDetailSection({ campaignId }: { campaignId: string }) {
  const campaignQuery = useNeuroCampaign(campaignId)
  const lifecycle = useCampaignLifecycleMutation(campaignId)
  const campaign = campaignQuery.data

  if (campaignQuery.isLoading || !campaign) {
    return <Skeleton className="h-32 w-full" />
  }

  const isDraft = campaign.status === 'draft'
  const isRunning = campaign.status === 'running'
  const isPaused = campaign.status === 'paused'

  return (
    <Card className="space-y-4 p-4">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-base font-semibold text-gray-900">{campaign.name}</h2>
          {campaign.description ? <p className="mt-0.5 text-sm text-gray-500">{campaign.description}</p> : null}
        </div>
        <CampaignStatusBadge status={campaign.status} />
      </div>

      <div className="grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <span className="text-gray-500">Режим</span>
          <p className="font-medium">{campaign.mode}</p>
        </div>
        <div>
          <span className="text-gray-500">Отправка</span>
          <p className="font-medium">{campaign.send_mode}</p>
        </div>
        <div>
          <span className="text-gray-500">Одобрение</span>
          <p className="font-medium">{campaign.approval_mode}</p>
        </div>
        <div>
          <span className="text-gray-500">Dry Run</span>
          <p className="font-medium">{campaign.dry_run ? 'Да' : 'Нет'}</p>
        </div>
      </div>

      <div className="flex gap-2">
        {isDraft || isPaused ? (
          <Button
            size="sm"
            variant="primary"
            icon={<Play className="size-3.5" />}
            onClick={() => lifecycle.mutate('start')}
            disabled={lifecycle.isPending}
          >
            Запустить
          </Button>
        ) : null}
        {isRunning ? (
          <Button
            size="sm"
            variant="secondary"
            icon={<Pause className="size-3.5" />}
            onClick={() => lifecycle.mutate('pause')}
            disabled={lifecycle.isPending}
          >
            Пауза
          </Button>
        ) : null}
        {isRunning || isPaused ? (
          <Button
            size="sm"
            variant="danger"
            icon={<Square className="size-3.5" />}
            onClick={() => lifecycle.mutate('stop')}
            disabled={lifecycle.isPending}
          >
            Остановить
          </Button>
        ) : null}
      </div>
    </Card>
  )
}
