import { Button, SectionCard } from '@stylisttg/ui'
import { useState } from 'react'

export function SubmitPasswordForm({
  disabled,
  onSubmitPassword,
}: {
  disabled?: boolean
  onSubmitPassword: (password: string) => Promise<void>
}) {
  const [password, setPassword] = useState('')

  return (
    <SectionCard title="Введите пароль 2FA" description="Пароль не сохраняется в интерфейсе и очищается после отправки.">
      <form
        className="flex flex-col gap-3 sm:flex-row"
        onSubmit={(event) => {
          event.preventDefault()
          const value = password
          setPassword('')
          void onSubmitPassword(value)
        }}
      >
        <input
          aria-label="Пароль 2FA"
          autoComplete="current-password"
          className="h-10 flex-1 rounded-md border border-border px-3 text-sm"
          disabled={disabled}
          onChange={(event) => setPassword(event.target.value)}
          placeholder="Пароль 2FA"
          type="password"
          value={password}
        />
        <Button disabled={disabled || password.trim().length === 0} type="submit">
          Отправить пароль
        </Button>
      </form>
    </SectionCard>
  )
}
