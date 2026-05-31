import { AlertCircle, CheckCircle2, Clock, Users } from 'lucide-react'
import type React from 'react'

import type { AccountReadinessRiskSummary } from '@/lib/api'
import { accountStats } from '@/lib/accounts'

export function StatsRow({ stats }: { stats: ReturnType<typeof accountStats> }) {
  return (
    <div className="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
      <StatCard icon={<Users className="size-4 text-primary" />} label="Всего" value={stats.total} />
      <StatCard
        icon={<CheckCircle2 className="size-4 text-primary" />}
        label="Авторизованы"
        tone="primary"
        value={stats.authorized}
      />
      <StatCard
        icon={<Clock className="size-4 text-muted-foreground" />}
        label="Ожидают"
        tone="muted"
        value={stats.waiting}
      />
      <StatCard
        icon={<AlertCircle className="size-4 text-muted-foreground" />}
        label="Ошибки"
        tone="muted"
        value={stats.error}
      />
    </div>
  )
}

export function RiskSummaryRow({ summary }: { summary: AccountReadinessRiskSummary }) {
  return (
    <section className="mb-4 rounded-xl border border-border bg-card px-4 py-3 shadow-sm">
      <div className="mb-2 flex items-center justify-between gap-3">
        <div className="text-sm font-bold text-foreground">Риск аккаунтов</div>
        <div className="text-[11px] font-semibold text-muted-foreground">app-known readiness score</div>
      </div>
      <div className="grid gap-2 sm:grid-cols-4">
        <RiskMetric label="Низкий" value={summary.low} className="bg-muted text-primary" />
        <RiskMetric label="Средний" value={summary.medium} className="bg-muted text-muted-foreground" />
        <RiskMetric label="Высокий" value={summary.high} className="bg-muted text-muted-foreground" />
        <RiskMetric label="Критический" value={summary.critical} className="bg-destructive/10 text-destructive" />
      </div>
    </section>
  )
}


function RiskMetric({ className, label, value }: { className: string; label: string; value: number }) {
  return (
    <div className={`rounded-lg px-3 py-2 text-xs font-semibold ${className}`}>
      <div>{label}</div>
      <div className="mt-1 text-lg font-bold">{value}</div>
    </div>
  )
}

export function BatchSafetySummary({
  counts,
  canStart,
}: {
  counts: Record<string, number>
  canStart: boolean
}) {
  const items = [
    ['Готовы', counts.ready ?? 0, 'text-primary bg-muted'],
    ['Нужен вход', counts.needs_login ?? 0, 'text-destructive bg-destructive/10'],
    ['На паузе', counts.paused ?? 0, 'text-muted-foreground bg-muted'],
    ['Ограничения', counts.limited ?? 0, 'text-muted-foreground bg-muted'],
    ['Неизвестно', counts.unknown ?? 0, 'text-muted-foreground bg-muted'],
  ] as const
  return (
    <section className="mb-4 rounded-xl border border-border bg-card px-4 py-3 shadow-sm">
      <div className="mb-2 flex items-center justify-between gap-3">
        <div className="text-sm font-bold text-foreground">Готовность массовых действий</div>
        <div className={`text-[11px] font-semibold ${canStart ? 'text-primary' : 'text-muted-foreground'}`}>
          {canStart ? 'Можно запускать' : 'Есть ограничения'}
        </div>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {items.map(([label, value, className]) => (
          <span className={`rounded-full px-2 py-1 text-[11px] font-semibold ${className}`} key={label}>
            {label}: {value}
          </span>
        ))}
      </div>
    </section>
  )
}

function StatCard({
  icon,
  label,
  tone = 'default',
  value,
}: {
  icon: React.ReactNode
  label: string
  tone?: 'default' | 'primary' | 'muted'
  value: number
}) {
  const color = {
    default: 'text-foreground bg-muted',
    primary: 'text-primary bg-muted',
    muted: 'text-muted-foreground bg-muted',
  }[tone]

  return (
    <div className="stat-card flex items-center gap-3 rounded-xl border border-border bg-card px-4 py-3">
      <div className={`flex size-9 items-center justify-center rounded-lg ${color}`}>{icon}</div>
      <div>
        <p className={`text-lg font-bold leading-none ${tone === 'default' ? 'text-foreground' : color.split(' ')[0]}`}>
          {value}
        </p>
        <p className="mt-0.5 text-[11px] text-muted-foreground">{label}</p>
      </div>
    </div>
  )
}
