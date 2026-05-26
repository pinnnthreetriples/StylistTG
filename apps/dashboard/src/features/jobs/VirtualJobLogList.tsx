import { useVirtualizer } from '@tanstack/react-virtual'
import { EmptyState } from '@stylisttg/ui'
import { useRef } from 'react'

import { createDemoJobLogRows, type JobLogEntry } from '@/features/jobs/jobLogModel'

export function VirtualJobLogList({
  entries = createDemoJobLogRows(),
  isLoading = false,
}: {
  entries?: JobLogEntry[]
  isLoading?: boolean
}) {
  if (isLoading) return <div className="rounded-lg border border-border bg-card p-6 text-sm text-muted-foreground">Загружаем журнал...</div>
  if (entries.length === 0) {
    return (
      <EmptyState
        title="Задач пока нет"
        description="Создайте задачу из карточки аккаунта после проверки риска."
      />
    )
  }
  if (typeof window === 'undefined') return <StaticJobLogList entries={entries.slice(0, 25)} />
  return <VirtualJobLogListBrowser entries={entries} />
}

function StaticJobLogList({ entries }: { entries: JobLogEntry[] }) {
  return (
    <div className="rounded-lg border border-border bg-card">
      {entries.map((entry) => (
        <JobLogRow entry={entry} key={entry.id} />
      ))}
    </div>
  )
}

function VirtualJobLogListBrowser({ entries }: { entries: JobLogEntry[] }) {
  const parentRef = useRef<HTMLDivElement>(null)
  // TanStack Virtual intentionally returns virtualizer helpers that React Compiler cannot memoize.
  // eslint-disable-next-line react-hooks/incompatible-library
  const virtualizer = useVirtualizer({
    count: entries.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 48,
    overscan: 8,
  })

  return (
    <div className="h-[520px] overflow-auto rounded-lg border border-border bg-card" ref={parentRef}>
      <div className="relative w-full" style={{ height: `${virtualizer.getTotalSize()}px` }}>
        {virtualizer.getVirtualItems().map((virtualItem) => {
          const entry = entries[virtualItem.index]
          return (
            <div
              className="absolute left-0 top-0 w-full"
              key={entry.id}
              style={{ transform: `translateY(${virtualItem.start}px)` }}
            >
              <JobLogRow entry={entry} />
            </div>
          )
        })}
      </div>
    </div>
  )
}

function JobLogRow({ entry }: { entry: JobLogEntry }) {
  const tone = entry.level === 'error' ? 'text-destructive' : entry.level === 'warning' ? 'text-muted-foreground' : 'text-muted-foreground'
  const levelLabel = entry.level === 'error' ? 'Ошибка' : entry.level === 'warning' ? 'Внимание' : 'Инфо'
  return (
    <div className="grid grid-cols-[11rem_5rem_1fr] gap-3 border-b border-border px-4 py-3 text-xs">
      <span className="font-mono text-muted-foreground">{entry.timestamp}</span>
      <span className={`font-bold ${tone}`}>{levelLabel}</span>
      <span className="truncate text-foreground">{entry.message}</span>
    </div>
  )
}
