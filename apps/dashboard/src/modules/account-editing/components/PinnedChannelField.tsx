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
        className="mb-1 block text-[11px] font-semibold uppercase tracking-wider text-gray-500"
        htmlFor="pinned-channel"
      >
        Закрепить канал в профиле
      </label>
      <div className="relative">
        <Input
          className="h-9 rounded-lg border-gray-200 bg-gray-50/50 hover:bg-white focus:bg-white px-3 text-sm transition-colors font-mono"
          id="pinned-channel"
          onChange={(e) => onChange(e.target.value || null)}
          value={value ?? ''}
          placeholder="ID или username канала"
        />
        {(currentValue ?? '') !== (value ?? '') && (
          <span className="absolute right-2.5 top-1/2 -translate-y-1/2 size-1.5 rounded-full bg-tangerine-400" />
        )}
      </div>
    </div>
  )
}
