import { SectionCard } from '@stylisttg/ui'

import { formatWarmupEventPayload, WARMUP_EVENT_LABELS } from '../labels'
import type { WarmupEvent } from '../types'

export function WarmupEventLog({ events }: { events: WarmupEvent[] }) {
  return (
    <SectionCard title="Журнал событий" description="Аудит действий и переходов выбранной сессии.">
      <div className="grid gap-2">
        {events.length === 0 ? <p className="text-sm text-gray-500">Событий пока нет.</p> : null}
        {events.map((event) => (
          <div className="rounded-lg border border-gray-200 bg-white px-3 py-2 shadow-sm" key={event.id}>
            <div className="flex items-center justify-between gap-3">
              <span className="text-sm font-semibold text-navy-900">
                {WARMUP_EVENT_LABELS[event.event_type] ?? event.event_type}
              </span>
              <span className="text-xs text-gray-400">{new Date(event.created_at).toLocaleString('ru-RU')}</span>
            </div>
            <p className="mt-1 text-xs leading-5 text-gray-600">{formatWarmupEventPayload(event)}</p>
            {Object.keys(event.payload).length > 0 ? (
              <details className="mt-2">
                <summary className="cursor-pointer text-xs font-medium text-gray-400">Технические данные</summary>
                <pre className="mt-2 max-h-28 overflow-auto rounded-md bg-gray-50 p-2 text-xs text-gray-500">
                  {JSON.stringify(event.payload, null, 2)}
                </pre>
              </details>
            ) : null}
          </div>
        ))}
      </div>
    </SectionCard>
  )
}
