import { Loader2 } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

type AuthPhoneStepProps = {
  phoneNumber: string
  pending: boolean
  onPhoneNumberChange: (value: string) => void
  onSubmit: () => void
}

export function AuthPhoneStep({
  phoneNumber,
  pending,
  onPhoneNumberChange,
  onSubmit,
}: AuthPhoneStepProps) {
  return (
    <form
      className="space-y-4"
      onSubmit={(event) => {
        event.preventDefault()
        onSubmit()
      }}
    >
      <div className="space-y-1.5">
        <label className="block text-xs font-medium text-muted-foreground" htmlFor="auth-phone-number">
          Номер телефона
        </label>
        <Input
          autoComplete="tel"
          className="h-auto rounded-xl border-border bg-card px-3.5 py-3 text-sm"
          id="auth-phone-number"
          inputMode="tel"
          onChange={(event) => onPhoneNumberChange(event.target.value)}
          placeholder="+7 999 111 22 33"
          value={phoneNumber}
        />
      </div>
      <Button
        className="h-auto w-full rounded-xl bg-primary px-4 py-3 text-sm font-semibold text-primary-foreground hover:bg-primary"
        disabled={pending || !phoneNumber.trim()}
        type="submit"
      >
        {pending ? <Loader2 className="size-4 animate-spin" /> : null}
        Получить код
      </Button>
    </form>
  )
}
