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
    <SectionCard title="Submit 2FA password" description="Password is never persisted in the UI and is cleared after submit.">
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
          autoComplete="current-password"
          className="h-10 flex-1 rounded-md border border-gray-200 px-3 text-sm"
          disabled={disabled}
          onChange={(event) => setPassword(event.target.value)}
          placeholder="2FA password"
          type="password"
          value={password}
        />
        <Button disabled={disabled || password.trim().length === 0} type="submit">
          Submit password
        </Button>
      </form>
    </SectionCard>
  )
}
