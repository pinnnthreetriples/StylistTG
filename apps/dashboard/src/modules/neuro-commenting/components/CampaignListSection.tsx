import { Button, Card, EmptyState, Input } from '@stylisttg/ui'
import { Plus } from 'lucide-react'
import { useState } from 'react'

import { useCreateNeuroCampaign, useNeuroCampaigns } from '../hooks'
import type { NeuroCampaign } from '../types'

import { CampaignStatusBadge } from './CampaignStatusBadge'

export function CampaignListSection({
  selectedId,
  onSelect,
}: {
  selectedId: string | null
  onSelect: (id: string) => void
}) {
  const campaignsQuery = useNeuroCampaigns()
  const createMutation = useCreateNeuroCampaign()
  const [showCreate, setShowCreate] = useState(false)
  const [newName, setNewName] = useState('')

  const campaigns: NeuroCampaign[] = campaignsQuery.data?.items ?? []
  const mutationError = createMutation.isError ? 'Не удалось сохранить изменения' : null

  const handleCreate = () => {
    if (!newName.trim()) return
    createMutation.mutate(
      { name: newName.trim() },
      {
        onSuccess: (created) => {
          setNewName('')
          setShowCreate(false)
          onSelect(created.id)
        },
      },
    )
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-foreground">Кампании</h2>
        <Button size="sm" variant="outline" onClick={() => setShowCreate((v) => !v)} icon={<Plus className="size-3.5" />}>
          Создать
        </Button>
      </div>

      {showCreate ? (
        <Card className="grid gap-2 p-3">
          <div className="flex items-center gap-2">
            <Input
              className="flex-1"
              placeholder="Название кампании"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
            />
            <Button size="sm" onClick={handleCreate} disabled={createMutation.isPending || !newName.trim()}>
              Добавить
            </Button>
          </div>
          {mutationError ? <p className="text-xs font-medium text-destructive">{mutationError}</p> : null}
        </Card>
      ) : null}

      {campaignsQuery.isError ? (
        <Card className="p-4 text-sm text-destructive">Не удалось загрузить данные</Card>
      ) : null}

      {campaigns.length === 0 && !campaignsQuery.isLoading && !campaignsQuery.isError ? (
        <EmptyState title="Нет кампаний" description="Создайте первую кампанию для начала работы" />
      ) : null}

      <div className="space-y-1.5">
        {campaigns.map((campaign) => (
          <button
            key={campaign.id}
            type="button"
            onClick={() => onSelect(campaign.id)}
            className={`flex w-full items-center justify-between rounded-lg border px-3 py-2.5 text-left text-sm transition ${
              selectedId === campaign.id
                ? 'border-border bg-muted text-foreground'
                : 'border-border bg-card text-foreground hover:bg-muted'
            }`}
          >
            <span className="truncate font-medium">{campaign.name}</span>
            <CampaignStatusBadge status={campaign.status} />
          </button>
        ))}
      </div>
    </div>
  )
}
