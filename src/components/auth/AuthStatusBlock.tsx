import { labelIssue } from '@/lib/uiLabels'

type AuthStatusBlockProps = {
  title: string
  description: string
  accent: 'neutral' | 'error'
  errorCode?: string | null
}

export function AuthStatusBlock({
  title,
  description,
  accent,
  errorCode,
}: AuthStatusBlockProps) {
  const palette =
    accent === 'error'
      ? 'border-red-200/70 bg-red-50 text-red-800'
      : 'border-gray-200/70 bg-gray-50 text-gray-700'

  return (
    <div className={`rounded-2xl border px-4 py-3 ${palette}`}>
      <p className="text-sm font-semibold">{title}</p>
      <p className="mt-1 text-xs leading-5">{description}</p>
      {errorCode ? <p className="mt-2 text-[10px] opacity-70">{labelIssue(errorCode)}</p> : null}
    </div>
  )
}
