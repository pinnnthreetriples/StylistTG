import { Button, SectionCard } from '@stylisttg/ui'
import { useState } from 'react'

export function StartAuthForm({
  disabled,
  onStart,
}: {
  disabled?: boolean
  onStart: (payload: { phone_number: string; label?: string }) => Promise<void>
}) {
  const [phoneNumber, setPhoneNumber] = useState('')
  const [label, setLabel] = useState('')

  return (
    <SectionCard
      title="Start real Telegram auth"
      description="Creates a controlled TDLib auth session. Live runtime remains disabled unless backend operators explicitly enable it."
    >
      <form
        className="grid gap-3 md:grid-cols-[1fr_1fr_auto]"
        onSubmit={(event) => {
          event.preventDefault()
          void onStart({ phone_number: phoneNumber, label: label.trim() || undefined })
        }}
      >
        <label className="grid gap-1 text-sm font-medium text-gray-700">
          Phone number
          <input
            className="h-10 rounded-md border border-gray-200 px-3 text-sm"
            disabled={disabled}
            onChange={(event) => setPhoneNumber(event.target.value)}
            placeholder="+123456789"
            value={phoneNumber}
          />
        </label>
        <label className="grid gap-1 text-sm font-medium text-gray-700">
          Label
          <input
            className="h-10 rounded-md border border-gray-200 px-3 text-sm"
            disabled={disabled}
            onChange={(event) => setLabel(event.target.value)}
            placeholder="Operator note"
            value={label}
          />
        </label>
        <Button className="self-end" disabled={disabled || phoneNumber.trim().length < 5} type="submit">
          Start auth
        </Button>
      </form>
    </SectionCard>
  )
}
