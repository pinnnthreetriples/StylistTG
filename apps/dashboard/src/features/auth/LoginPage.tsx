import { useNavigate } from '@tanstack/react-router'
import { LogIn, Sparkles, UserPlus } from 'lucide-react'
import { useState, type FormEvent } from 'react'

import { useSupabaseAuth } from '@/features/auth/SupabaseAuthContext'

type LoginMode = 'login' | 'signup'

export function LoginPage() {
  const navigate = useNavigate()
  const { error, signIn, signUp, status } = useSupabaseAuth()
  const [mode, setMode] = useState<LoginMode>('login')
  const [pending, setPending] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  const handleSubmit = async ({ email, password }: { email: string; password: string }) => {
    setPending(true)
    setMessage(null)
    try {
      if (mode === 'login') {
        if (await signIn(email, password)) {
          void navigate({ to: '/home', replace: true })
        }
      } else {
        if (await signUp(email, password)) {
          setMessage('Аккаунт создан. Подтвердите email по ссылке из письма.')
        }
      }
    } finally {
      setPending(false)
    }
  }

  return (
    <LoginPageView
      error={status === 'unconfigured' ? 'Supabase не настроен. Проверьте переменные окружения.' : error}
      message={message}
      mode={mode}
      onModeChange={setMode}
      onSubmit={handleSubmit}
      pending={pending}
    />
  )
}

export function LoginPageView({
  error,
  message,
  mode,
  onModeChange,
  onSubmit,
  pending,
}: {
  error?: string | null
  message?: string | null
  mode: LoginMode
  onModeChange: (mode: LoginMode) => void
  onSubmit: (payload: { email: string; password: string }) => void | Promise<void>
  pending: boolean
}) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    void onSubmit({ email, password })
  }

  return (
    <main className="min-h-screen bg-background px-4 py-8 text-foreground">
      <section className="mx-auto flex min-h-[calc(100vh-4rem)] max-w-md flex-col justify-center">
        <div className="mb-6 flex items-center gap-2">
          <div className="flex size-10 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <Sparkles className="size-4" />
          </div>
          <div>
            <h1 className="font-sans text-2xl font-bold">Войти в StylistTG</h1>
            <p className="mt-1 text-sm text-muted-foreground">SaaS dashboard</p>
          </div>
        </div>

        <form className="grid gap-4 rounded-lg border border-border bg-card p-5 shadow-sm" onSubmit={submit}>
          <label className="grid gap-1.5 text-sm font-semibold text-foreground">
            Email
            <input
              aria-label="Email"
              autoComplete="email"
              className="h-11 rounded-lg border border-border px-3 text-sm font-medium outline-none transition focus:border-border"
              onChange={(event) => setEmail(event.target.value)}
              required
              type="email"
              value={email}
            />
          </label>
          <label className="grid gap-1.5 text-sm font-semibold text-foreground">
            Пароль
            <input
              aria-label="Пароль"
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
              className="h-11 rounded-lg border border-border px-3 text-sm font-medium outline-none transition focus:border-border"
              minLength={6}
              onChange={(event) => setPassword(event.target.value)}
              required
              type="password"
              value={password}
            />
          </label>

          {error ? <div className="rounded-lg border border-destructive/20 bg-destructive/10 px-3 py-2 text-sm font-medium text-destructive">{error}</div> : null}
          {message ? <div className="rounded-lg border border-border bg-muted px-3 py-2 text-sm font-medium text-primary">{message}</div> : null}

          <button
            className="flex h-11 items-center justify-center gap-2 rounded-lg bg-primary px-4 text-sm font-bold text-primary-foreground transition hover:bg-primary disabled:opacity-60"
            disabled={pending}
            type="submit"
          >
            {mode === 'login' ? <LogIn className="size-4" /> : <UserPlus className="size-4" />}
            {mode === 'login' ? 'Войти' : 'Создать аккаунт'}
          </button>

          <button
            className="h-10 rounded-lg text-sm font-semibold text-primary transition hover:bg-muted"
            onClick={() => onModeChange(mode === 'login' ? 'signup' : 'login')}
            type="button"
          >
            {mode === 'login' ? 'Создать аккаунт' : 'Войти'}
          </button>
        </form>
      </section>
    </main>
  )
}
