import { Card, EmptyState, Skeleton } from '@stylisttg/ui'

import { useNeuroEvents } from '../hooks'

export function EventsSection({ campaignId }: { campaignId: string | undefined }) {
  const eventsQuery = useNeuroEvents(campaignId)
  const events = eventsQuery.data?.items ?? []

  if (eventsQuery.isError) {
    return <Card className="p-4 text-sm text-destructive">Не удалось загрузить данные</Card>
  }
  if (eventsQuery.isLoading) return <Skeleton className="h-40 w-full" />

  return (
    <Card className="p-4">
      <h3 className="mb-3 text-sm font-semibold text-foreground">
        События ({eventsQuery.data?.total ?? 0})
      </h3>
      {events.length === 0 ? (
        <EmptyState title="Нет событий" description="События появятся при работе кампании" />
      ) : (
        <div className="max-h-96 space-y-1.5 overflow-y-auto">
          {events.map((event) => (
            <div key={event.id} className="flex items-start gap-2 rounded border border-border px-3 py-2 text-sm">
              <span className="shrink-0 text-xs text-muted-foreground">
                {new Date(event.created_at).toLocaleString('ru-RU', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
              </span>
              <span className="text-foreground">{event.message}</span>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}
