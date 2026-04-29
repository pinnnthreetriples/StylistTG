import { AlertTriangle, X } from 'lucide-react'
import { Button } from '@/components/ui/button'

interface ErrorBannerProps {
  banner: {
    title: string
    description: string
    accent: 'error' | 'warning'
  }
}

export function ErrorBanner({ banner }: ErrorBannerProps) {
  const palette =
    banner.accent === 'error'
      ? 'border-red-200/60 bg-red-50 text-red-800'
      : 'border-honey-200/60 bg-honey-50 text-honey-700'

  return (
    <section
      className={`ui-surface-enter mb-6 flex flex-col gap-3 rounded-2xl border p-4 sm:flex-row sm:items-start ${palette}`}
    >
      <div className="flex size-8 flex-shrink-0 items-center justify-center rounded-lg bg-white/70">
        <AlertTriangle className="size-4 text-current" />
      </div>
      <div className="min-w-0 flex-1">
        <h4 className="text-sm font-semibold">{banner.title}</h4>
        <p className="mt-0.5 text-xs">{banner.description}</p>
      </div>
      <Button
        aria-label="Закрыть ошибку"
        className="h-auto rounded-lg px-2 py-1.5 text-current/70 hover:text-current"
        variant="ghost"
      >
        <X className="size-3.5" />
      </Button>
    </section>
  )
}
