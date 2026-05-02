import { Loader2 } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

type AuthCodeStepProps = {
  code: string
  pending: boolean
  phoneNumber: string
  onCodeChange: (value: string) => void
  onSubmit: () => void
  onResetPhone: () => void
}

export function AuthCodeStep({
  code,
  pending,
  phoneNumber,
  onCodeChange,
  onSubmit,
  onResetPhone,
}: AuthCodeStepProps) {
  return (
    <form
      className="space-y-4"
      onSubmit={(event) => {
        event.preventDefault()
        onSubmit()
      }}
    >
      <div className="space-y-1">
        <p className="text-xs font-medium text-gray-500">Код отправлен на {phoneNumber || 'указанный номер'}</p>
        <button
          className="text-xs font-medium text-navy-500 transition-colors hover:text-navy-600"
          onClick={onResetPhone}
          type="button"
        >
          Изменить номер
        </button>
      </div>
      <div className="space-y-1.5">
        <label className="block text-xs font-medium text-gray-500" htmlFor="auth-code">
          Код подтверждения
        </label>
        <Input
          autoComplete="one-time-code"
          className="h-auto rounded-xl border-gray-200 bg-white px-3.5 py-3 text-sm tracking-[0.2em]"
          id="auth-code"
          inputMode="numeric"
          onChange={(event) => onCodeChange(event.target.value)}
          placeholder="12345"
          value={code}
        />
      </div>
      <Button
        className="h-auto w-full rounded-xl bg-navy-400 px-4 py-3 text-sm font-semibold text-white hover:bg-navy-500"
        disabled={pending || !code.trim()}
        type="submit"
      >
        {pending ? <Loader2 className="size-4 animate-spin" /> : null}
        Подтвердить код
      </Button>
    </form>
  )
}
