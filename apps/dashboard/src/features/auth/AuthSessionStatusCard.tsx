import { SectionCard, StatusPill } from '@stylisttg/ui'

import type { TelegramAuthSession } from '@/lib/api'
import { labelAuthSessionStatus, labelIssue } from '@/lib/uiLabels'

export function AuthSessionStatusCard({ session }: { session: TelegramAuthSession | null }) {
  const status = session?.status ?? 'not_started'
  const tone = status === 'ready' ? 'green' : status === 'failed' ? 'red' : status.includes('waiting') ? 'amber' : 'muted'

  return (
    <SectionCard
      title="Статус авторизации"
      description="Вход выполняется только по явному действию, с аудитом, лимитами и блокировкой live-режима по умолчанию."
    >
      <div className="flex flex-wrap items-center gap-2">
        <StatusPill tone={tone}>{labelAuthSessionStatus(status)}</StatusPill>
        {session?.requires_code ? <StatusPill tone="amber">Нужен код</StatusPill> : null}
        {session?.requires_password ? <StatusPill tone="amber">Нужен пароль 2FA</StatusPill> : null}
        {session?.cooldown_until ? <StatusPill tone="red">Пауза безопасности</StatusPill> : null}
      </div>
      {session?.last_error_code ? (
        <p className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
          {labelIssue(session.last_error_code)}
        </p>
      ) : null}
      <details className="mt-4 rounded-lg border border-gray-100 bg-gray-50 px-3 py-2 text-xs text-gray-600">
        <summary className="cursor-pointer font-semibold text-gray-800">Расширенная диагностика</summary>
        <dl className="mt-3 grid gap-3 md:grid-cols-3">
          <div>
            <dt className="text-gray-500">Сессия входа</dt>
            <dd className="font-mono text-xs text-gray-900">{session?.id ?? 'Не создана'}</dd>
          </div>
          <div>
            <dt className="text-gray-500">Аккаунт</dt>
            <dd className="font-mono text-xs text-gray-900">{session?.account_id ?? 'Ожидает входа'}</dd>
          </div>
          <div>
            <dt className="text-gray-500">Код ошибки</dt>
            <dd className="font-mono text-xs text-gray-900">{session?.last_error_code ?? 'Нет'}</dd>
          </div>
        </dl>
      </details>
    </SectionCard>
  )
}
