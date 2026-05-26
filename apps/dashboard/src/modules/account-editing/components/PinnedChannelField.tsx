import { Input } from '@/components/ui/input'

export function PinnedChannelField({
  value,
  currentValue,
  onChange,
}: {
  value: string | null
  currentValue: string | null
  onChange: (next: string | null) => void
}) {
  return (
    <div>
      <label
        className="mb-1 block text-[11px] font-semibold uppercase tracking-wider text-muted-foreground"
        htmlFor="pinned-channel"
      >
        Закрепить канал в профиле
      </label>
      <div className="relative">
        <Input
          className="h-9 rounded-lg border-border bg-muted hover:bg-card focus:bg-card px-3 text-sm transition-colors font-mono"
          id="pinned-channel"
          onChange={(e) => onChange(e.target.value || null)}
          value={value ?? ''}
          placeholder="ID или username канала"
        />
        {(currentValue ?? '') !== (value ?? '') && (
          <span className="absolute right-2.5 top-1/2 -translate-y-1/2 size-1.5 rounded-full bg-muted" />
        )}
      </div>
    </div>
  )
}
