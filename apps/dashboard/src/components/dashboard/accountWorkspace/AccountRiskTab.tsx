import { RiskSummaryCard, RiskReasonList, SectionCard, CooldownPill, AccountReadinessPanel } from '@stylisttg/ui'

import { AnimatedSection } from '@/components/ui/AnimatedSection'
import {
  labelAccountState,
  labelProxyStatus,
  labelRiskLevel,
  labelRiskReason,
  labelRuntimeHealth,
  runtimeHealthTone,
} from '@/lib/uiLabels'
import type { AccountRisk } from '@/features/accounts/accountRisk'
import { validityCheckSummary, type AccountValidityCheck } from '@/lib/accountSafety'

export type AccountRiskTabProps = {
  risk?: AccountRisk | null
  validityChecks?: AccountValidityCheck[]
  cooldowns?: Array<{ operation: string; expires_at: string }>
  accountState?: string
  runtimeHealth?: string
  proxyStatus?: string
}

function formatCooldownRemaining(expiresAt: string): string {
  const remaining = new Date(expiresAt).getTime() - Date.now()
  if (remaining <= 0) return 'Истекла'
  const minutes = Math.ceil(remaining / 60_000)
  if (minutes < 60) return `${minutes} мин`
  return `${Math.floor(minutes / 60)} ч ${minutes % 60} мин`
}

export function AccountRiskTab({
  risk,
  validityChecks = [],
  cooldowns = [],
  accountState,
  runtimeHealth,
  proxyStatus,
}: AccountRiskTabProps) {
  const riskLevel = risk?.level ?? 'low'
  const riskScore = risk?.score ?? 0

  const readinessItems = [
    {
      label: 'Авторизация',
      ready: accountState === 'execution_usable' || accountState === 'authorized_ready',
      detail: labelAccountState(accountState),
    },
    {
      label: 'Среда исполнения',
      ready: runtimeHealthTone(runtimeHealth) === 'green',
      detail: labelRuntimeHealth(runtimeHealth),
    },
    {
      label: 'Прокси',
      ready: proxyStatus !== 'failed' && proxyStatus !== 'tdlib_failed',
      detail: labelProxyStatus(proxyStatus ?? 'none'),
    },
  ]

  const mappedReasons = (risk?.reasons ?? []).map((r) => ({
    code: r.code,
    severity: r.severity,
    message: labelRiskReason(r.code) !== r.code ? labelRiskReason(r.code) : r.message,
  }))

  return (
    <AnimatedSection className="mx-auto grid max-w-6xl gap-5 px-4 py-6 sm:px-6">
      {/* Risk Summary */}
      <RiskSummaryCard
        level={riskLevel}
        levelLabel={labelRiskLevel(riskLevel)}
        score={riskScore}
        description={
          riskLevel === 'low'
            ? 'Аккаунт в хорошем состоянии и готов к работе.'
            : riskLevel === 'medium'
              ? 'Есть незначительные проблемы, которые стоит устранить.'
              : riskLevel === 'high'
                ? 'Обнаружены серьёзные проблемы. Рекомендуется действие.'
                : 'Аккаунт заблокирован или требует немедленного вмешательства.'
        }
      />

      {/* Reasons */}
      <SectionCard title="Причины риска">
        <RiskReasonList
          reasons={mappedReasons}
          emptyMessage="Проблем не обнаружено."
        />
      </SectionCard>

      {/* Readiness */}
      <AccountReadinessPanel
        title="Готовность аккаунта"
        items={readinessItems}
      />

      {/* Cooldowns */}
      {cooldowns.length > 0 ? (
        <SectionCard title="Активные паузы безопасности">
          <div className="flex flex-wrap gap-2">
            {cooldowns.map((cd) => (
              <CooldownPill
                key={cd.operation}
                remainingLabel={`${cd.operation}: ${formatCooldownRemaining(cd.expires_at)}`}
              />
            ))}
          </div>
        </SectionCard>
      ) : null}

      {/* Validity check history */}
      <SectionCard title="История проверок безопасности">
        {validityChecks.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Проверка ещё не запускалась. Кнопка «Проверить» не меняет аккаунт, а только проверяет сессию.
          </p>
        ) : (
          <div className="space-y-1.5">
            {validityChecks.slice(0, 5).map((check) => (
              <details className="rounded-lg bg-muted px-3 py-2 text-xs text-muted-foreground" key={check.id}>
                <summary className="cursor-pointer font-semibold text-foreground">{validityCheckSummary(check)}</summary>
                <pre aria-label="Расширенная диагностика" className="mt-2 max-h-40 overflow-auto rounded bg-card p-2 text-[11px] text-muted-foreground">
                  {JSON.stringify({ status: check.status, error_code: check.error_code, details: check.details, result: check.result }, null, 2)}
                </pre>
              </details>
            ))}
          </div>
        )}
      </SectionCard>
    </AnimatedSection>
  )
}
