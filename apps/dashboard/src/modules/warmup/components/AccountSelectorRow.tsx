import { Button, StatusPill, type StatusPillTone } from '@stylisttg/ui'
import { ChevronsLeft, ChevronsRight } from 'lucide-react'

import type { WarmupSelectableAccount } from '../types'

const VALIDITY_LABELS: Record<WarmupSelectableAccount['validity_badge'], string> = {
  blocked: 'Блок',
  needs_login: 'Нужен вход',
  unknown: 'Не проверен',
  valid: 'Валидный',
}

const PROXY_LABELS: Record<WarmupSelectableAccount['proxy_badge'], string> = {
  issue: 'Прокси issue',
  missing: 'Без прокси',
  ok: 'Прокси ОК',
  unknown: 'Прокси ?',
}

const PHASE_LABELS: Record<WarmupSelectableAccount['phase_badge'], string> = {
  in_work: 'В работе',
  new: 'Новый',
  warming: 'Прогревается',
}

const VALIDITY_TONES: Record<WarmupSelectableAccount['validity_badge'], StatusPillTone> = {
  blocked: 'red',
  needs_login: 'amber',
  unknown: 'muted',
  valid: 'green',
}

const PROXY_TONES: Record<WarmupSelectableAccount['proxy_badge'], StatusPillTone> = {
  issue: 'amber',
  missing: 'muted',
  ok: 'green',
  unknown: 'muted',
}

const PHASE_TONES: Record<WarmupSelectableAccount['phase_badge'], StatusPillTone> = {
  in_work: 'amber',
  new: 'muted',
  warming: 'warn',
}

export function AccountSelectorRow({
  account,
  direction,
  onMove,
}: {
  account: WarmupSelectableAccount
  direction: 'add' | 'remove'
  onMove: (accountId: string) => void
}) {
  const label = account.display_name || account.username || account.phone_number
  const icon = direction === 'add' ? <ChevronsRight className="size-4" /> : <ChevronsLeft className="size-4" />
  return (
    <div className="grid min-h-20 grid-cols-[minmax(0,1fr)_2.25rem] items-center gap-3 border-b border-border px-3 py-2 last:border-b-0">
      <div className="min-w-0">
        <div className="flex min-w-0 items-center gap-2">
          <span className="truncate text-sm font-semibold text-foreground">{label}</span>
          <span className="shrink-0 text-xs font-medium text-muted-foreground">{account.country_iso}</span>
        </div>
        <div className="mt-0.5 truncate text-xs text-muted-foreground">
          {account.username ? `@${account.username} · ` : ''}
          {account.phone_number} · {account.account_id.slice(0, 8)}
        </div>
        <div className="mt-2 flex flex-wrap gap-1.5">
          <StatusPill tone={VALIDITY_TONES[account.validity_badge]}>{VALIDITY_LABELS[account.validity_badge]}</StatusPill>
          <StatusPill tone={PROXY_TONES[account.proxy_badge]}>{PROXY_LABELS[account.proxy_badge]}</StatusPill>
          <StatusPill tone={PHASE_TONES[account.phase_badge]}>{PHASE_LABELS[account.phase_badge]}</StatusPill>
          {account.tags.slice(0, 3).map((tag) => (
            <span className="rounded-md border border-border px-1.5 py-0.5 text-[11px] text-muted-foreground" key={tag}>
              {tag}
            </span>
          ))}
        </div>
      </div>
      <Button
        aria-label={direction === 'add' ? `Добавить ${label}` : `Удалить ${label}`}
        className="size-9 px-0"
        type="button"
        variant="outline"
        onClick={() => onMove(account.account_id)}
      >
        {icon}
      </Button>
    </div>
  )
}
