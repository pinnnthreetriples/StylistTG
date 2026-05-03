import { Button, SectionCard } from '@stylisttg/ui'
import { useState } from 'react'

export function SubmitCodeForm({
  disabled,
  onSubmitCode,
}: {
  disabled?: boolean
  onSubmitCode: (code: string) => Promise<void>
}) {
  const [code, setCode] = useState('')

  return (
    <SectionCard title="Submit Telegram code" description="Code is sent once and cleared from browser state after submit.">
      <form
        className="flex flex-col gap-3 sm:flex-row"
        onSubmit={(event) => {
          event.preventDefault()
          const value = code
          setCode('')
          void onSubmitCode(value)
        }}
      >
        <input
          autoComplete="one-time-code"
          className="h-10 flex-1 rounded-md border border-gray-200 px-3 text-sm"
          disabled={disabled}
          onChange={(event) => setCode(event.target.value)}
          placeholder="Telegram code"
          value={code}
        />
        <Button disabled={disabled || code.trim().length === 0} type="submit">
          Submit code
        </Button>
      </form>
    </SectionCard>
  )
}
