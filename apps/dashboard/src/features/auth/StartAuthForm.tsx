import { Button, SectionCard } from '@stylisttg/ui'
import { useState } from 'react'

import type { LiveStatus } from '@/lib/liveStatus'

export function StartAuthForm({
  disabled,
  liveStatus,
  onStart,
}: {
  disabled?: boolean
  liveStatus: LiveStatus
  onStart: (payload: { phone_number: string; label?: string }) => Promise<void>
}) {
  const [phoneNumber, setPhoneNumber] = useState('')
  const [label, setLabel] = useState('')

  return (
    <SectionCard
      title="Введите номер телефона"
      description={`Создаёт контролируемую сессию входа. ${liveStatus.label}.`}
    >
      <form
        className="grid gap-3 md:grid-cols-[1fr_1fr_auto]"
        onSubmit={(event) => {
          event.preventDefault()
          void onStart({ phone_number: phoneNumber, label: label.trim() || undefined })
        }}
      >
        <label className="grid gap-1 text-sm font-medium text-foreground">
          Номер телефона
          <input
            aria-label="Номер телефона"
            className="h-10 rounded-md border border-border px-3 text-sm"
            disabled={disabled}
            onChange={(event) => setPhoneNumber(event.target.value)}
            placeholder="+123456789"
            value={phoneNumber}
          />
        </label>
        <label className="grid gap-1 text-sm font-medium text-foreground">
          Название
          <input
            aria-label="Название пакета авторизации"
            className="h-10 rounded-md border border-border px-3 text-sm"
            disabled={disabled}
            onChange={(event) => setLabel(event.target.value)}
            placeholder="Например: рабочий аккаунт"
            value={label}
          />
        </label>
        <Button className="self-end" disabled={disabled || phoneNumber.trim().length < 5} type="submit">
          Создать пакет авторизации
        </Button>
      </form>
    </SectionCard>
  )
}
