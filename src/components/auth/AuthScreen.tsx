import { HelpCircle, KeyRound, Loader2, ShieldCheck, Sparkles } from 'lucide-react'
import { memo } from 'react'

import { AuthCodeStep } from '@/components/auth/AuthCodeStep'
import { AuthPasswordStep } from '@/components/auth/AuthPasswordStep'
import { AuthPhoneStep } from '@/components/auth/AuthPhoneStep'
import { AuthStatusBlock } from '@/components/auth/AuthStatusBlock'

type AuthScreenProps = {
  step: 'phone' | 'code' | 'password'
  phase: 'auth-loading' | 'auth-phone' | 'auth-code' | 'auth-password' | 'auth-refreshing' | 'auth-error'
  phoneNumber: string
  code: string
  password: string
  passwordHint: string | null
  errorMessage: { title: string; description: string } | null
  errorCode?: string | null
  testDcEnabled: boolean
  testDcPending: boolean
  onPhoneNumberChange: (value: string) => void
  onCodeChange: (value: string) => void
  onPasswordChange: (value: string) => void
  onTestDcChange: (enabled: boolean) => void
  onStart: () => void
  onConfirm: () => void
  onSubmitPassword: () => void
  onResetPhone: () => void
}

export const AuthScreen = memo(function AuthScreen({
  step,
  phase,
  phoneNumber,
  code,
  password,
  passwordHint,
  errorMessage,
  errorCode,
  testDcEnabled,
  testDcPending,
  onPhoneNumberChange,
  onCodeChange,
  onPasswordChange,
  onTestDcChange,
  onStart,
  onConfirm,
  onSubmitPassword,
  onResetPhone,
}: AuthScreenProps) {
  const statusBlock =
    phase === 'auth-refreshing'
      ? {
          title: 'Подключаем аккаунт',
          description: 'Обновляем runtime и проверяем, что аккаунт готов к работе.',
          accent: 'neutral' as const,
        }
      : phase === 'auth-loading'
        ? {
            title: 'Проверяем состояние входа',
            description: 'Подождите немного, мы обновляем контекст аккаунта.',
            accent: 'neutral' as const,
          }
        : errorMessage
          ? {
              ...errorMessage,
              accent: 'error' as const,
            }
          : step === 'password'
            ? {
                title: 'Двухэтапная аутентификация',
                description: 'У вас включена защита паролем. Введите облачный пароль Telegram для завершения входа.',
                accent: 'neutral' as const,
              }
            : {
                title: step === 'phone' ? 'Вход только по коду' : 'Ожидаем код подтверждения',
                description:
                  step === 'phone'
                    ? 'Введите номер телефона в международном формате, чтобы начать вход.'
                    : 'Введите код из Telegram. После подтверждения мы автоматически обновим runtime.',
                accent: 'neutral' as const,
              }

  const pending = phase === 'auth-loading' || phase === 'auth-refreshing'
  const safetyTips = [
    'Входите один раз: если код уже отправлен, дождитесь его и не запрашивайте новый без причины.',
    'Для тестов используйте отдельный аккаунт, а не основной рабочий Telegram.',
    'Не меняйте сеть или VPN во время входа: Telegram видит новую сессию как новый клиент.',
  ]

  return (
    <div className="min-h-screen bg-cream gradient-blob">
      <div className="mx-auto flex min-h-screen max-w-[1400px] items-center justify-center px-4 py-10 sm:px-6">
        <section className="w-full max-w-[980px] overflow-hidden rounded-[28px] border border-gray-200/60 bg-white shadow-soft">
          <div className="grid gap-0 lg:grid-cols-[0.9fr_1.1fr]">
            <div className="border-b border-gray-200/60 bg-gradient-to-br from-navy-50 via-white to-tangerine-50 p-6 lg:border-b-0 lg:border-r lg:p-8">
              <div className="flex items-center gap-3">
                <div className="flex size-10 items-center justify-center rounded-xl bg-navy-400">
                  <Sparkles className="size-5 text-white" />
                </div>
                <div>
                  <p className="text-lg font-bold text-navy-900">StylistTG</p>
                  <p className="text-xs font-medium text-gray-400">Авторизация по коду</p>
                </div>
              </div>

              <div className="mt-10 max-w-sm">
                <h1 className="text-3xl font-bold tracking-normal text-navy-900">Вход в Telegram</h1>
                <p className="mt-3 text-sm leading-6 text-gray-600">
                  Рабочий экран авторизации перед панелью управления. После успешного входа вы сразу попадёте в
                  редактирование профиля.
                </p>
              </div>

              <div className="mt-8 grid gap-3 text-sm text-gray-600">
                <div className="flex items-start gap-3 rounded-2xl bg-white/80 px-4 py-3 shadow-soft">
                  <ShieldCheck className="mt-0.5 size-4 text-emerald-600" />
                  <div>
                    <p className="font-medium text-navy-900">Поддержка двухэтапной аутентификации</p>
                    <p className="mt-1 text-xs leading-5 text-gray-500">OTP-код + облачный пароль Telegram (2FA).</p>
                  </div>
                </div>
                <div className="flex items-start gap-3 rounded-2xl bg-white/80 px-4 py-3 shadow-soft">
                  {pending ? (
                    <Loader2 className="mt-0.5 size-4 animate-spin text-navy-500" />
                  ) : (
                    <KeyRound className="mt-0.5 size-4 text-navy-500" />
                  )}
                  <div>
                    <p className="font-medium text-navy-900">После входа обновляем runtime</p>
                    <p className="mt-1 text-xs leading-5 text-gray-500">
                      В панель управления пускаем только когда аккаунт действительно готов к работе.
                    </p>
                  </div>
                </div>
              </div>
            </div>

            <div className="p-6 lg:p-8">
              <div className="mx-auto max-w-md">
                <div className="mb-6">
                  <AuthStatusBlock
                    accent={statusBlock.accent}
                    description={statusBlock.description}
                    errorCode={errorMessage ? errorCode : null}
                    title={statusBlock.title}
                  />
                </div>
                <div className="mb-5 flex items-center justify-between gap-3 rounded-xl border border-gray-200 bg-white px-4 py-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="text-xs font-semibold text-navy-900">Test DC</p>
                      <div className="group relative flex">
                        <HelpCircle className="size-4 text-gray-400" aria-label="Подсказка по Test DC" />
                        <div className="pointer-events-none absolute left-1/2 top-6 z-10 w-64 -translate-x-1/2 rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs leading-5 text-gray-600 opacity-0 shadow-soft transition-opacity group-hover:opacity-100">
                          Тестовый Telegram. Пример: номер +9996611234, код 11111. Для реального аккаунта выключите.
                        </div>
                      </div>
                    </div>
                    <p className="mt-1 text-xs leading-5 text-gray-500">
                      {testDcEnabled ? 'Вход идет в тестовую среду Telegram.' : 'Вход идет в обычный Telegram.'}
                    </p>
                  </div>
                  <button
                    aria-checked={testDcEnabled}
                    aria-label="Переключить Test DC"
                    className={`relative h-6 w-11 shrink-0 rounded-full border transition-colors ${
                      testDcEnabled ? 'border-emerald-500 bg-emerald-500' : 'border-gray-300 bg-gray-200'
                    } ${testDcPending || pending ? 'opacity-60' : 'hover:border-gray-400'}`}
                    disabled={testDcPending || pending}
                    onClick={() => onTestDcChange(!testDcEnabled)}
                    role="switch"
                    type="button"
                  >
                    <span
                      className={`absolute left-0.5 top-0.5 size-5 rounded-full bg-white shadow-sm transition-transform ${
                        testDcEnabled ? 'translate-x-5' : 'translate-x-0'
                      }`}
                    />
                  </button>
                </div>

                {step === 'phone' ? (
                  <AuthPhoneStep
                    onPhoneNumberChange={onPhoneNumberChange}
                    onSubmit={onStart}
                    pending={pending}
                    phoneNumber={phoneNumber}
                  />
                ) : step === 'password' ? (
                  <AuthPasswordStep
                    password={password}
                    pending={pending}
                    phoneNumber={phoneNumber}
                    passwordHint={passwordHint}
                    onPasswordChange={onPasswordChange}
                    onSubmit={onSubmitPassword}
                    onResetPhone={onResetPhone}
                  />
                ) : (
                  <AuthCodeStep
                    code={code}
                    onCodeChange={onCodeChange}
                    onResetPhone={onResetPhone}
                    onSubmit={onConfirm}
                    pending={pending}
                    phoneNumber={phoneNumber}
                  />
                )}
                <div className="mt-6 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3">
                  <p className="text-xs font-semibold text-navy-900">Как входить безопаснее</p>
                  <ul className="mt-2 space-y-1.5 text-xs leading-5 text-gray-600">
                    {safetyTips.map((tip) => (
                      <li className="flex gap-2" key={tip}>
                        <span className="mt-2 size-1 shrink-0 rounded-full bg-amber-500" />
                        <span>{tip}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  )
})
