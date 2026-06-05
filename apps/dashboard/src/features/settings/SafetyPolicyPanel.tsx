import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { SectionCard, Select, StatusCard, StatusPill } from '@stylisttg/ui'
import { ShieldCheck } from 'lucide-react'

import { updateWorkspaceSafetyPolicy } from '@/lib/api'
import {
  updateWorkspaceSafetyPolicyInCache,
  workspaceSafetyPolicyQueryOptions,
} from '@/lib/queries'

type SafetyPolicyPanelProps = {
  currentUserRole?: string
}

type SafetyMode = 'conservative' | 'balanced' | 'aggressive'

const MODE_LABELS: Record<SafetyMode, string> = {
  conservative: 'Conservative',
  balanced: 'Balanced',
  aggressive: 'Aggressive',
}

const MODE_TONES: Record<SafetyMode, 'green' | 'amber' | 'red'> = {
  conservative: 'green',
  balanced: 'amber',
  aggressive: 'red',
}

export function SafetyPolicyPanel({ currentUserRole }: SafetyPolicyPanelProps) {
  const queryClient = useQueryClient()
  const policyQuery = useQuery(workspaceSafetyPolicyQueryOptions())
  const adminCanEdit = currentUserRole === 'admin' || currentUserRole === 'owner'
  const policy = policyQuery.data
  const temporarilyDisabled = policy?.temporarily_disabled === true
  const canEdit = adminCanEdit && !temporarilyDisabled
  const updateMutation = useMutation({
    mutationFn: (mode: SafetyMode) => updateWorkspaceSafetyPolicy({ mode }),
    onSuccess: (nextPolicy) => updateWorkspaceSafetyPolicyInCache(queryClient, nextPolicy),
  })

  return (
    <SectionCard
      title="AI-защита рабочей области"
      description="Единая policy для задержек, имитации поведения, прогрева, прокси и автопауз."
      actions={
        policy ? (
          <StatusPill tone={temporarilyDisabled ? 'amber' : MODE_TONES[policy.mode as SafetyMode]}>
            {temporarilyDisabled ? 'Отключено' : MODE_LABELS[policy.mode as SafetyMode]}
          </StatusPill>
        ) : null
      }
    >
      {policyQuery.isPending ? (
        <div className="text-sm text-muted-foreground">Загрузка policy...</div>
      ) : policyQuery.isError || !policy ? (
        <div className="text-sm text-muted-foreground">Policy безопасности недоступна.</div>
      ) : temporarilyDisabled ? (
        <div
          className="rounded-md border border-amber-300 bg-amber-50 px-3 py-3 text-sm text-amber-900"
          role="status"
        >
          <div className="mb-1 font-semibold">Временно отключено</div>
          <p>
            AI-защита рабочей области неактивна — поведенческие ограничения,
            тихие часы и автопаузы не применяются. Настройки сохранены и не
            редактируются до повторного включения.
          </p>
        </div>
      ) : (
        <div className="grid gap-4">
          <div className="grid gap-2 sm:grid-cols-[minmax(0,240px)_1fr] sm:items-center">
            <label className="text-sm font-medium text-foreground" htmlFor="workspace-safety-mode">
              Режим защиты
            </label>
            <Select
              disabled={!canEdit || updateMutation.isPending}
              id="workspace-safety-mode"
              value={policy.mode}
              onChange={(event) => updateMutation.mutate(event.currentTarget.value as SafetyMode)}
            >
              <option value="conservative">Conservative</option>
              <option value="balanced">Balanced</option>
              <option value="aggressive">Aggressive</option>
            </Select>
          </div>

          {!canEdit ? (
            <div className="rounded-md border border-border bg-muted px-3 py-2 text-xs text-muted-foreground">
              Только администратор может менять режим.
            </div>
          ) : null}
          {updateMutation.error ? (
            <div className="rounded-md border border-destructive/20 bg-destructive/10 px-3 py-2 text-xs text-destructive">
              Не удалось сохранить policy.
            </div>
          ) : null}

          <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
            <StatusCard
              label="Задержки"
              value={`x${formatNumber(policy.delay_multiplier)}`}
              detail="множитель"
              tone="neutral"
            />
            <StatusCard
              label="Скорость ввода"
              value={formatTypingSpeed(policy.typing_chars_per_minute_min, policy.typing_chars_per_minute_max)}
              detail="typing"
              tone="neutral"
            />
            <StatusCard
              label="Тихие часы"
              value={formatQuietHours(policy.quiet_hours_local_start, policy.quiet_hours_local_end)}
              detail="local time"
              tone="neutral"
            />
            <StatusCard
              label="Карантин FloodWait"
              value={`${policy.quarantine_hours_on_flood_wait} ч`}
              detail="автопауза"
              tone="neutral"
            />
          </div>

          <div className="grid gap-3 text-sm lg:grid-cols-2">
            <ParameterList
              title="Behavior"
              items={[
                ['Просмотр профиля', formatPercent(policy.profile_view_probability)],
                ['Скролл', formatPercent(policy.scroll_probability)],
                ['Опечатки', formatPercent(policy.typo_probability)],
                ['Удаление сообщения', formatPercent(policy.message_deletion_probability)],
              ]}
            />
            <ParameterList
              title="Protection"
              items={[
                ['Прогрев перед комментингом', policy.require_warmup_before_commenting ? 'required' : 'optional'],
                ['Минимум дней прогрева', String(policy.min_warmup_days)],
                ['Здоровый прокси', policy.require_healthy_proxy ? 'required' : 'optional'],
                ['Возраст аккаунта', `${policy.min_account_age_hours} ч`],
                ['FloodWait streak', `>=${policy.auto_pause_on_flood_wait_count}`],
                ['Deleted-comments streak', `>=${policy.auto_pause_on_deleted_comments_count}`],
              ]}
            />
          </div>
        </div>
      )}
    </SectionCard>
  )
}

function ParameterList({ title, items }: { title: string; items: Array<[string, string]> }) {
  return (
    <div className="rounded-md border border-border bg-card">
      <div className="flex items-center gap-2 border-b border-border px-3 py-2 text-xs font-semibold uppercase text-muted-foreground">
        <ShieldCheck className="size-3.5" />
        {title}
      </div>
      <dl className="divide-y divide-gray-100">
        {items.map(([label, value]) => (
          <div className="grid grid-cols-[1fr_auto] gap-3 px-3 py-2" key={label}>
            <dt className="text-muted-foreground">{label}</dt>
            <dd className="font-medium text-foreground">{value}</dd>
          </div>
        ))}
      </dl>
    </div>
  )
}

function formatNumber(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(1)
}

function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`
}

function formatTypingSpeed(min: number | null, max: number | null): string {
  if (min === null || max === null) return 'disabled'
  return `${min}-${max} зн/мин`
}

function formatQuietHours(start: number | null, end: number | null): string {
  if (start === null || end === null) return 'none'
  return `${formatMinuteOfDay(start)}-${formatMinuteOfDay(end)}`
}

function formatMinuteOfDay(value: number): string {
  const hours = Math.floor(value / 60)
  const minutes = value % 60
  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}`
}
