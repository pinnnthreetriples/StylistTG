import { Link } from '@tanstack/react-router'
import { Button, MetricCard, PageHeader, PageShell } from '@stylisttg/ui'
import { AlertTriangle, CheckCircle2, LogIn, Plus, ShieldAlert, Users } from 'lucide-react'

import type { AccountRisk, AccountRiskSummary } from '@/features/accounts/accountRisk'
import { AccountsTable } from '@/features/accounts/AccountsTable'
import type { AccountListItem } from '@/lib/api'
import { AnimatedPage } from '@/components/ui/AnimatedPage'

export function AccountsPage({
  accounts,
  isLoading,
  onSelectAccount,
  riskByAccount,
  riskSummary,
  onAddAccounts,
  userId,
  workspaceId,
}: {
  accounts: AccountListItem[]
  isLoading?: boolean
  onSelectAccount?: (accountId: string) => void
  riskByAccount?: Map<string, AccountRisk>
  riskSummary?: AccountRiskSummary
  onAddAccounts?: () => void
  userId?: string | null
  workspaceId?: string | null
}) {
  const readyCount = accounts.filter((account) => account.is_execution_usable).length
  const attentionCount = (riskSummary?.medium ?? 0) + (riskSummary?.high ?? 0) + (riskSummary?.critical ?? 0)

  return (
    <AnimatedPage>
      <PageShell className="grid gap-6">
        <PageHeader
          eyebrow="Аккаунты"
          title="Аккаунты"
          description="Управляйте Telegram-аккаунтами, рисками, прокси и задачами."
          actions={
            onAddAccounts ? (
              <Button onClick={onAddAccounts} type="button" variant="secondary">
                <Plus className="size-4" />
                Добавить аккаунты
              </Button>
            ) : (
              <Link to="/accounts/add">
                <Button type="button" variant="secondary">
                  <Plus className="size-4" />
                  Добавить аккаунты
                </Button>
              </Link>
            )
          }
        />
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
          <MetricCard icon={<Users className="size-4" />} label="Всего" value={isLoading ? '...' : accounts.length} />
          <MetricCard icon={<CheckCircle2 className="size-4" />} label="Готовы" value={isLoading ? '...' : readyCount} />
          <MetricCard icon={<AlertTriangle className="size-4" />} label="Требуют внимания" value={riskSummary ? attentionCount : '...'} />
          <MetricCard icon={<ShieldAlert className="size-4" />} label="Высокий риск" value={riskSummary ? riskSummary.high + riskSummary.critical : '...'} />
          <MetricCard icon={<LogIn className="size-4" />} label="Нужен вход" value={riskSummary?.reauth_required ?? '...'} />
          <MetricCard label="Без прокси" value={riskSummary?.proxy_problem ?? '...'} />
        </div>
        <AccountsTable
          accounts={accounts}
          isLoading={isLoading}
          onSelectAccount={onSelectAccount}
          riskByAccount={riskByAccount}
          userId={userId}
          workspaceId={workspaceId}
        />
      </PageShell>
    </AnimatedPage>
  )
}
