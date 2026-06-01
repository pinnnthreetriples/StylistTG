import { AlertTriangle, Check, ChevronRight, Clock, FlaskConical, Server, Trash2 } from 'lucide-react'
import { useState } from 'react'

import { buildAssetContentUrl, type AccountListItem } from '@/lib/api'
import {
  activeCooldownLabels,
  compactSafetyReasons,
  compactSafetyStatusLabel,
  compactSafetyTone,
  riskLevelLabel,
  type AccountSafetySummary,
} from '@/lib/accountSafety'
import { accountStats, accountStatus, maskPhone } from '@/lib/accounts'
import { proxyStatusLabel, proxyStatusTone, type AccountProxySummary } from '@/lib/proxy'

export function AccountRow({
  account,
  index,
  isLast,
  onSelectAccount,
  onPrefetchAccount,
  onRequestDelete,
  safety,
  proxy,
}: {
  account: AccountListItem
  index: number
  isLast: boolean
  onSelectAccount: (accountId: string) => void
  onPrefetchAccount: (accountId: string) => void
  onRequestDelete: (account: AccountListItem) => void
  safety: AccountSafetySummary | null
  proxy: AccountProxySummary | null
}) {
  const status = accountStatus(account)
  const name = account.display_name || account.phone_number
  const initial = name.slice(0, 1).toUpperCase()
  const statusStyle = statusStyles[status.kind]
  const StatusIcon = statusStyle.icon

  return (
    <div
      className={`account-row  d${Math.min(index + 2, 12)} group flex w-full items-center gap-3.5 px-4 py-3 text-left transition-all ${
        isLast ? '' : 'border-b border-border'
      } ${status.kind === 'error' ? 'bg-muted' : ''}`}
    >
      <button
        className="flex min-w-0 flex-1 items-center gap-3.5 text-left"
        onFocus={() => onPrefetchAccount(account.account_id)}
        onMouseEnter={() => onPrefetchAccount(account.account_id)}
        onClick={() => onSelectAccount(account.account_id)}
        type="button"
      >
        <AccountAvatar account={account} fallbackClassName={avatarGradient(index)} initial={initial} />
        <div className="min-w-0 flex-1">
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            <p className="truncate text-sm font-semibold text-foreground">{name}</p>
            <span className={`inline-flex shrink-0 items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium ${statusStyle.badge}`}>
              <StatusIcon className="size-2.5" />
              {status.label}
            </span>
            {account.is_test_dc ? (
              <span className="inline-flex shrink-0 items-center gap-1 rounded bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
                <FlaskConical className="size-2.5" />
                Test DC
              </span>
            ) : null}
            <SafetyBadge safety={safety} />
            <ProxyBadge proxy={proxy} />
          </div>
          <p className={`mt-0.5 truncate text-xs ${status.kind === 'error' ? 'text-muted-foreground' : 'text-muted-foreground'}`}>
            {account.username ? `@${account.username} · ` : ''}
            {maskPhone(account.phone_number)}
          </p>
          {safety ? (
            <p className="mt-0.5 truncate text-[11px] text-muted-foreground">
              {accountSafetyDetails(safety)}
            </p>
          ) : null}
        </div>
      </button>
      <div className="flex shrink-0 items-center gap-2">
        <span className={`hidden text-[11px] lg:inline ${statusStyle.detail}`}>
          {status.kind === 'authorized' ? updatedAgo(account.updated_at) : status.detail}
        </span>
        <button
          aria-label={`Удалить аккаунт ${name}`}
          className="flex size-8 items-center justify-center rounded-lg text-muted-foreground transition-all hover:bg-destructive/10 hover:text-destructive"
          onClick={() => onRequestDelete(account)}
          title="Удалить аккаунт"
          type="button"
        >
          <Trash2 className="size-4" />
        </button>
        <ChevronRight className="row-chevron size-5 text-muted-foreground transition-all group-hover:translate-x-0.5 group-hover:text-primary" />
      </div>
    </div>
  )
}

function ProxyBadge({ proxy }: { proxy: AccountProxySummary | null }) {
  const tone = proxyStatusTone(proxy?.status)
  const classes = {
    green: 'bg-muted text-primary',
    amber: 'bg-muted text-muted-foreground',
    red: 'bg-destructive/10 text-destructive',
    gray: 'bg-muted text-muted-foreground',
  }[tone]
  return (
    <span
      className={`inline-flex shrink-0 items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium ${classes}`}
      title="Proxy используется для сетевой маршрутизации аккаунта и диагностики подключения."
    >
      {proxyStatusLabel(proxy?.status)}
    </span>
  )
}

function SafetyBadge({ safety }: { safety: AccountSafetySummary | null }) {
  if (!safety) return null
  const tone = compactSafetyTone(safety)
  const classes = {
    green: 'bg-muted text-primary',
    amber: 'bg-muted text-muted-foreground',
    red: 'bg-destructive/10 text-destructive',
    gray: 'bg-muted text-muted-foreground',
  }[tone]

  return (
    <span className={`inline-flex shrink-0 items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium ${classes}`}>
      {compactSafetyStatusLabel(safety)}
    </span>
  )
}

function accountSafetyDetails(safety: AccountSafetySummary): string {
  const cooldowns = activeCooldownLabels(safety)
  if (cooldowns.length > 0) return cooldowns.join(' · ')
  return compactSafetyReasons(safety).join(' · ') || riskLevelLabel(safety.overall_risk_level)
}

function AccountAvatar({
  account,
  fallbackClassName,
  initial,
}: {
  account: AccountListItem
  fallbackClassName: string
  initial: string
}) {
  const [failedAssetId, setFailedAssetId] = useState<string | null>(null)

  if (account.profile_photo_asset_id && failedAssetId !== account.profile_photo_asset_id) {
    return (
      <img
        alt=""
        className="size-10 shrink-0 rounded-full object-cover"
        onError={() => setFailedAssetId(account.profile_photo_asset_id)}
        src={buildAssetContentUrl(account.profile_photo_asset_id)}
      />
    )
  }

  return (
    <div className={`flex size-10 shrink-0 items-center justify-center rounded-full text-sm font-bold text-primary-foreground ${fallbackClassName}`}>
      {initial}
    </div>
  )
}

const statusStyles = {
  authorized: {
    icon: Check,
    badge: 'bg-muted text-primary',
    detail: 'text-muted-foreground',
  },
  waiting: {
    icon: Clock,
    badge: 'bg-muted text-muted-foreground',
    detail: 'text-muted-foreground',
  },
  error: {
    icon: AlertTriangle,
    badge: 'bg-destructive/10 text-destructive',
    detail: 'text-muted-foreground',
  },
}

function avatarGradient(index: number): string {
  const gradients = [
    'bg-muted  ',
    'bg-muted  ',
    'bg-muted  ',
    'bg-muted  ',
    'bg-muted  ',
    'bg-muted  ',
    'bg-muted  ',
    'bg-muted  ',
  ]
  return gradients[index % gradients.length]
}

function updatedAgo(value: string): string {
  const timestamp = Date.parse(value)
  if (!Number.isFinite(timestamp)) return 'Недавно'

  const diffMinutes = Math.max(0, Math.round((Date.now() - timestamp) / 60000))
  if (diffMinutes < 1) return 'Сейчас'
  if (diffMinutes < 60) return `${diffMinutes} мин. назад`

  const diffHours = Math.round(diffMinutes / 60)
  if (diffHours < 24) return `${diffHours} ч назад`
  return `${Math.round(diffHours / 24)} дн назад`
}

export function FooterCounter({ stats }: { stats: ReturnType<typeof accountStats> }) {
  return (
    <div className="mt-4 flex flex-col gap-2 px-1 text-xs text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
      <p>
        Всего: <span className="font-medium text-muted-foreground">{stats.total} аккаунтов</span>
        <span className="mx-1.5 text-muted-foreground">·</span>
        <span className="font-medium text-primary">{stats.authorized} авторизованы</span>
        <span className="mx-1.5 text-muted-foreground">·</span>
        <span className="font-medium text-muted-foreground">{stats.waiting} ожидают</span>
        <span className="mx-1.5 text-muted-foreground">·</span>
        <span className="font-medium text-muted-foreground">{stats.error} ошибки</span>
      </p>
      <div className="flex items-center gap-1">
        <Server className="size-3.5" />
        TDLib · FastAPI · RQ · PostgreSQL
      </div>
    </div>
  )
}
