/**
 * Phase 1 · proxy snapshot panel.
 *
 * Показывает срез прокси, сделанный в момент создания сессии прогрева
 * (frozen routing snapshot — без credentials). Это основной артефакт для
 * аудита datacenter-policy и geo-match решений будущим live-движком.
 */
import { Badge, SectionCard } from '@stylisttg/ui'
import { Globe2 } from 'lucide-react'

import type { ProxyCategory, WarmupProxySnapshot } from '../types'

const CATEGORY_LABELS: Record<ProxyCategory, string> = {
  datacenter: 'Datacenter',
  residential: 'Residential',
  mobile: 'Mobile',
  unknown: 'Неизвестно',
}

const CATEGORY_TONES: Record<ProxyCategory, 'amber' | 'green' | 'blue' | 'gray'> = {
  datacenter: 'amber',
  residential: 'green',
  mobile: 'blue',
  unknown: 'gray',
}

export function WarmupProxySnapshotPanel({
  snapshot,
}: {
  snapshot: WarmupProxySnapshot | null | undefined
}) {
  if (!snapshot) {
    return (
      <SectionCard
        title="Прокси-снимок сессии"
        description="На момент создания сессии у аккаунта не было привязанного прокси."
      >
        <div className="rounded-lg border border-dashed border-border bg-muted px-4 py-3 text-sm text-muted-foreground">
          Без прокси live-режимы прогрева работать не будут. Привяжите прокси к
          аккаунту и пересоздайте сессию, если планируется shadow/network/advanced.
        </div>
      </SectionCard>
    )
  }
  const categoryKey = isKnownCategory(snapshot.proxy_category)
    ? snapshot.proxy_category
    : 'unknown'
  const lastChecked = formatTimestamp(snapshot.last_checked_at)
  return (
    <SectionCard
      title="Прокси-снимок сессии"
      description="Замороженные на момент создания сессии маршрутные поля. Credentials в снимок не входят."
    >
      <div className="grid gap-3 sm:grid-cols-2">
        <SnapshotRow label="Категория">
          <Badge tone={CATEGORY_TONES[categoryKey]}>
            <Globe2 className="size-3" />
            {CATEGORY_LABELS[categoryKey]}
          </Badge>
        </SnapshotRow>
        <SnapshotRow label="Тип">{snapshot.proxy_type}</SnapshotRow>
        <SnapshotRow label="Хост">
          <span className="font-mono text-xs">
            {snapshot.host}
            <span className="text-muted-foreground">:{snapshot.port}</span>
          </span>
        </SnapshotRow>
        <SnapshotRow label="Статус">
          {snapshot.status}
        </SnapshotRow>
        <SnapshotRow label="Последняя проверка">
          {lastChecked ?? '—'}
        </SnapshotRow>
      </div>
    </SectionCard>
  )
}

function SnapshotRow({
  label,
  children,
}: {
  label: string
  children: React.ReactNode
}) {
  return (
    <div className="grid gap-0.5">
      <span className="text-xs font-semibold uppercase text-muted-foreground">{label}</span>
      <span className="text-sm text-foreground">{children}</span>
    </div>
  )
}

function isKnownCategory(value: string): value is ProxyCategory {
  return value === 'datacenter' || value === 'residential' || value === 'mobile' || value === 'unknown'
}

function formatTimestamp(value: string | null): string | null {
  if (!value) return null
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return null
  return parsed.toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' })
}
