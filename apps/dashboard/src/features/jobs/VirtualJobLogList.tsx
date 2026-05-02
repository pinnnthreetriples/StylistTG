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
  if (isLoading) return <div className="rounded-lg border border-gray-200 bg-white p-6 text-sm text-gray-500">Loading logs...</div>
  if (entries.length === 0) {
    return (
      <EmptyState
        title="No job logs"
        description="Worker log entries will appear here when read-only endpoints are available."
      />
    )
  }
  if (typeof window === 'undefined') return <StaticJobLogList entries={entries.slice(0, 25)} />
  return <VirtualJobLogListBrowser entries={entries} />
}

function StaticJobLogList({ entries }: { entries: JobLogEntry[] }) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white">
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
    <div className="h-[520px] overflow-auto rounded-lg border border-gray-200 bg-white" ref={parentRef}>
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
  const tone = entry.level === 'error' ? 'text-red-600' : entry.level === 'warning' ? 'text-honey-700' : 'text-gray-600'
  return (
    <div className="grid grid-cols-[11rem_5rem_1fr] gap-3 border-b border-gray-100 px-4 py-3 text-xs">
      <span className="font-mono text-gray-400">{entry.timestamp}</span>
      <span className={`font-bold uppercase ${tone}`}>{entry.level}</span>
      <span className="truncate text-gray-700">{entry.message}</span>
    </div>
  )
}
