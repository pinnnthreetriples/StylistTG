import { Loader2 } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

type AuthPasswordStepProps = {
  password: string
  pending: boolean
  phoneNumber: string
  passwordHint: string | null
  onPasswordChange: (value: string) => void
  onSubmit: () => void
  onResetPhone: () => void
}

export function AuthPasswordStep({
  password,
  pending,
  phoneNumber,
  passwordHint,
  onPasswordChange,
  onSubmit,
  onResetPhone,
}: AuthPasswordStepProps) {
  return (
    <form
      className="space-y-4"
      onSubmit={(event) => {
        event.preventDefault()
        onSubmit()
      }}
    >
      <div className="space-y-1">
        <p className="text-xs font-medium text-muted-foreground">
          Двухэтапная аутентификация для {phoneNumber || 'указанный номер'}
        </p>
        <button
          className="text-xs font-medium text-primary transition-colors hover:text-primary"
          onClick={onResetPhone}
          type="button"
        >
          Изменить номер
        </button>
      </div>
      <div className="space-y-1.5">
        <label className="block text-xs font-medium text-muted-foreground" htmlFor="auth-password">
          Облачный пароль (2FA)
        </label>
        <Input
          autoComplete="current-password"
          className="h-auto rounded-xl border-border bg-card px-3.5 py-3 text-sm"
          id="auth-password"
          onChange={(event) => onPasswordChange(event.target.value)}
          placeholder="Введите пароль"
          type="password"
          value={password}
        />
        {passwordHint ? (
          <p className="text-xs text-muted-foreground">
            Подсказка: <span className="font-medium text-muted-foreground">{passwordHint}</span>
          </p>
        ) : null}
      </div>
      <Button
        className="h-auto w-full rounded-xl bg-primary px-4 py-3 text-sm font-semibold text-primary-foreground hover:bg-primary"
        disabled={pending || !password.trim()}
        type="submit"
      >
        {pending ? <Loader2 className="size-4 animate-spin" /> : null}
        Подтвердить пароль
      </Button>
    </form>
  )
}
