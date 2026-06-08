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
  aggressive: 'Permissive',
}

const MODE_TONES: Record<SafetyMode, 'green' | 'amber'> = {
  conservative: 'green',
  balanced: 'amber',
  aggressive: 'amber',
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
      title="Защитные пороги workspace"
      description="Workspace policy для прогрева, прокси, возраста аккаунта и автопауз."
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
            Защитные пороги workspace не применяются. Настройки сохранены и не
            редактируются, пока включён аварийный kill-switch.
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
              <option value="aggressive">Permissive</option>
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
              label="Прогрев"
              value={policy.require_warmup_before_commenting ? `${policy.min_warmup_days} д` : 'optional'}
              detail="перед комментингом"
              tone="neutral"
            />
            <StatusCard
              label="Прокси"
              value={policy.require_healthy_proxy ? 'required' : 'optional'}
              detail="health gate"
              tone="neutral"
            />
            <StatusCard
              label="Возраст аккаунта"
              value={`${policy.min_account_age_hours} ч`}
              detail="minimum"
              tone="neutral"
            />
            <StatusCard
              label="Карантин FloodWait"
              value={`${policy.quarantine_hours_on_flood_wait} ч`}
              detail="автопауза"
              tone="neutral"
            />
          </div>

          <div className="text-sm">
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
