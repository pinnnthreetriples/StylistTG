import { Button, PageHeader, SectionCard, StatusPill } from '@stylisttg/ui'
import { ShieldCheck } from 'lucide-react'
import { useState } from 'react'

import { AuthSessionStatusCard } from '@/features/auth/AuthSessionStatusCard'
import { StartAuthForm } from '@/features/auth/StartAuthForm'
import { SubmitCodeForm } from '@/features/auth/SubmitCodeForm'
import { SubmitPasswordForm } from '@/features/auth/SubmitPasswordForm'
import { redactAuthUiError } from '@/features/auth/authUiSecurity'
import {
  cancelTelegramAuthSession,
  createReauthSession,
  createTelegramAuthSession,
  submitTelegramAuthCode,
  submitTelegramAuthPassword,
  type TelegramAuthSession,
} from '@/lib/api'

export function AuthSessionWizard({ accountId }: { accountId?: string }) {
  const [session, setSession] = useState<TelegramAuthSession | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  async function run(action: () => Promise<TelegramAuthSession>) {
    setPending(true)
    setError(null)
    try {
      setSession(await action())
    } catch (currentError) {
      setError(currentError instanceof Error ? currentError.message : 'Действие авторизации не выполнено безопасно.')
    } finally {
      setPending(false)
    }
  }

  const selectedSessionId = session?.id

  return (
    <div className="grid gap-4">
      <PageHeader
        eyebrow="Авторизация"
        title={accountId ? 'Повторный вход в аккаунт' : 'Добавление одного аккаунта'}
        description="Безопасный вход через Telegram. Live-исполнение профиля, историй и музыки не запускается."
      />
      <SectionCard title="Защита операции">
        <div className="flex flex-wrap gap-2">
          <StatusPill tone="green">Только по вашему действию</StatusPill>
          <StatusPill tone="green">Запись в аудит</StatusPill>
          <StatusPill tone="green">Лимиты и блокировки</StatusPill>
          <StatusPill tone="amber">Live-режим выключен</StatusPill>
        </div>
      </SectionCard>
      <StartAuthForm
        disabled={pending}
        onStart={(payload) =>
          run(() => (accountId ? createReauthSession(accountId, payload) : createTelegramAuthSession(payload)))
        }
      />
      <AuthSessionStatusCard session={session} />
      {session?.requires_code && selectedSessionId ? (
        <SubmitCodeForm disabled={pending} onSubmitCode={(code) => run(() => submitTelegramAuthCode(selectedSessionId, { code }))} />
      ) : null}
      {session?.requires_password && selectedSessionId ? (
        <SubmitPasswordForm
          disabled={pending}
          onSubmitPassword={(password) => run(() => submitTelegramAuthPassword(selectedSessionId, { password }))}
        />
      ) : null}
      {selectedSessionId && session?.status !== 'canceled' ? (
        <div>
          <Button disabled={pending} onClick={() => void run(() => cancelTelegramAuthSession(selectedSessionId))} variant="secondary">
            Отменить вход
          </Button>
        </div>
      ) : null}
      {error ? (
        <div className="rounded-lg border border-amber-100 bg-amber-50 px-3 py-2 text-sm font-semibold text-amber-700">
          {redactAuthUiError(error)}
        </div>
      ) : null}
      <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-gray-500">
        <ShieldCheck className="size-4" />
        Коды и пароли не сохраняются в браузере.
      </div>
    </div>
  )
}
