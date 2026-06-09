import { Badge, Button, Input, SectionCard, Select, Tabs, TabsList, TabsTrigger } from '@stylisttg/ui'
import { ArrowDown, Radio, Search, WifiOff } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'

import { buildWarmupEventStreamUrl } from '../api'
import { useWarmupLiveEvents } from '../hooks'
import { WARMUP_EVENT_LABELS, WARMUP_EVENT_SEVERITY_LABELS } from '../labels'
import type {
  WarmupEventSeverity,
  WarmupLiveEvent,
  WarmupLiveEventPage,
} from '../types'

const SEVERITY_FILTERS: Array<WarmupEventSeverity | 'all'> = [
  'all',
  'info',
  'success',
  'warning',
  'error',
  'debug',
]

const SEVERITY_SYMBOLS: Record<WarmupEventSeverity, string> = {
  info: 'ⓘ',
  success: '✓',
  warning: '!',
  error: '×',
  debug: '·',
}

const SEVERITY_TONES: Record<WarmupEventSeverity, 'blue' | 'green' | 'amber' | 'red' | 'gray'> = {
  info: 'blue',
  success: 'green',
  warning: 'amber',
  error: 'red',
  debug: 'gray',
}

type WarmupLiveLogsProps = {
  eventsPage?: WarmupLiveEventPage
}

export function WarmupLiveLogs({ eventsPage }: WarmupLiveLogsProps) {
  const [accountId, setAccountId] = useState('all')
  const [severity, setSeverity] = useState<WarmupEventSeverity | 'all'>('all')
  const [search, setSearch] = useState('')
  const [liveEvents, setLiveEvents] = useState<WarmupLiveEvent[]>([])
  const [isOnline, setIsOnline] = useState(false)
  const bottomRef = useRef<HTMLDivElement | null>(null)
  const pageQuery = useWarmupLiveEvents({
    accountId: accountId === 'all' ? undefined : accountId,
    limit: 200,
  })
  const page = eventsPage ?? pageQuery.data

  const events = useMemo(
    () =>
      mergeEvents(page?.items ?? [], liveEvents).filter(
        (event) => accountId === 'all' || event.account_id === accountId,
      ),
    [accountId, liveEvents, page?.items],
  )

  useEffect(() => {
    if (typeof EventSource === 'undefined') return
    let cancelled = false
    let source: EventSource | null = null
    const cursor = page?.next_cursor ?? null

    void buildWarmupEventStreamUrl({
      accountId: accountId === 'all' ? undefined : accountId,
      cursor,
    }).then((url) => {
      if (cancelled) return
      source = new EventSource(url)
      source.onopen = () => setIsOnline(true)
      source.onerror = () => setIsOnline(false)
      source.onmessage = (message) => {
        const next = JSON.parse(message.data) as WarmupLiveEvent
        setLiveEvents((current) => mergeEvent(current, next))
      }
    })

    return () => {
      cancelled = true
      source?.close()
      setIsOnline(false)
    }
  }, [accountId, page?.next_cursor])

  const counters = useMemo(() => countBySeverity(events), [events])
  const filteredEvents = useMemo(
    () =>
      events.filter((event) => {
        if (severity !== 'all' && event.severity !== severity) return false
        if (!search.trim()) return true
        const query = search.trim().toLowerCase()
        return [
          event.account_label,
          event.phone_id,
          event.event_type,
          event.message,
          WARMUP_EVENT_LABELS[event.event_type] ?? '',
        ].some((value) => value.toLowerCase().includes(query))
      }),
    [events, search, severity],
  )

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: 'end' })
  }, [filteredEvents.length])

  const accounts = page?.accounts ?? []

  return (
    <SectionCard
      title="Live-логи"
      description="События прогрева по аккаунтам, уровням и тексту."
      actions={
        <Badge tone={isOnline ? 'green' : 'gray'}>
          {isOnline ? <Radio className="size-3" /> : <WifiOff className="size-3" />}
          {isOnline ? 'В прямом эфире' : 'Не в сети'}
        </Badge>
      }
    >
      <div className="grid gap-3">
        <div className="grid gap-2 lg:grid-cols-[minmax(0,1fr)_220px_minmax(180px,260px)]">
          <Tabs value={severity} onValueChange={(value) => setSeverity(value as WarmupEventSeverity | 'all')}>
            <TabsList className="flex w-full flex-wrap justify-start">
              {SEVERITY_FILTERS.map((filter) => (
                <TabsTrigger className="h-8 gap-1.5 px-2.5 text-xs" key={filter} value={filter}>
                  {WARMUP_EVENT_SEVERITY_LABELS[filter]} {filter === 'all' ? events.length : counters[filter]}
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>
          <Select
            aria-label="Фильтр аккаунта"
            value={accountId}
            onChange={(event) => setAccountId(event.target.value)}
          >
            <option value="all">Все аккаунты</option>
            {accounts.map((account) => (
              <option key={account.account_id} value={account.account_id}>
                {account.account_label}
              </option>
            ))}
          </Select>
          <label className="relative block">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              aria-label="Поиск по логам"
              className="pl-9"
              placeholder="Поиск"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </label>
        </div>
        <div className="max-h-[420px] overflow-y-auto rounded-lg border border-border">
          {filteredEvents.length === 0 ? (
            <div className="px-3 py-8 text-center text-sm text-muted-foreground">Событий по фильтрам нет.</div>
          ) : (
            <div className="divide-y divide-border">
              {filteredEvents.map((event) => (
                <WarmupLiveLogRow event={event} key={event.event_id} />
              ))}
              <div ref={bottomRef} />
            </div>
          )}
        </div>
        <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
          <span>
            Показано {filteredEvents.length} из {events.length} загруженных событий
          </span>
          <Button type="button" variant="outline" size="sm" onClick={() => bottomRef.current?.scrollIntoView()}>
            <ArrowDown className="size-4" />
            Вниз
          </Button>
        </div>
      </div>
    </SectionCard>
  )
}

function WarmupLiveLogRow({ event }: { event: WarmupLiveEvent }) {
  const time = new Date(event.occurred_at).toLocaleTimeString('ru-RU', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
  return (
    <div className="grid gap-1 px-3 py-2 text-sm sm:grid-cols-[86px_22px_minmax(0,1fr)] sm:items-start">
      <span className="font-mono text-xs text-muted-foreground">{time}</span>
      <span className={`text-sm font-semibold ${severityTextClass(event.severity)}`}>
        {SEVERITY_SYMBOLS[event.severity]}
      </span>
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-1.5">
          <Badge tone={SEVERITY_TONES[event.severity]}>{WARMUP_EVENT_SEVERITY_LABELS[event.severity]}</Badge>
          <span className="truncate font-medium text-foreground">{event.account_label}</span>
          <span className="text-muted-foreground">·</span>
          <span className="font-mono text-xs text-muted-foreground">{event.phone_id}</span>
        </div>
        <p className="mt-1 break-words text-sm leading-5 text-muted-foreground">
          {WARMUP_EVENT_LABELS[event.event_type] ?? event.message}
        </p>
      </div>
    </div>
  )
}

function countBySeverity(events: WarmupLiveEvent[]): Record<WarmupEventSeverity, number> {
  const counts: Record<WarmupEventSeverity, number> = {
    info: 0,
    success: 0,
    warning: 0,
    error: 0,
    debug: 0,
  }
  for (const event of events) {
    counts[event.severity] += 1
  }
  return counts
}

function mergeEvent(events: WarmupLiveEvent[], next: WarmupLiveEvent): WarmupLiveEvent[] {
  if (events.some((event) => event.event_id === next.event_id)) return events
  return [...events, next].slice(-500)
}

function mergeEvents(baseEvents: WarmupLiveEvent[], liveEvents: WarmupLiveEvent[]): WarmupLiveEvent[] {
  const merged = [...baseEvents]
  for (const event of liveEvents) {
    if (!merged.some((item) => item.event_id === event.event_id)) {
      merged.push(event)
    }
  }
  return merged.slice(-500)
}

function severityTextClass(severity: WarmupEventSeverity): string {
  if (severity === 'success') return 'text-emerald-700'
  if (severity === 'warning') return 'text-amber-700'
  if (severity === 'error') return 'text-red-700'
  if (severity === 'debug') return 'text-muted-foreground'
  return 'text-blue-700'
}
