import { AlertTriangle, CheckCircle2, Info, X } from 'lucide-react'

import { Button } from '@/components/ui/button'

export type ToastTone = 'success' | 'error' | 'info'

export type ToastItem = {
  id: string
  tone: ToastTone
  title: string
  description?: string
}

export function ToastViewport({
  onDismiss,
  toasts,
}: {
  onDismiss: (id: string) => void
  toasts: ToastItem[]
}) {
  if (toasts.length === 0) {
    return null
  }

  return (
    <div className="pointer-events-none fixed right-4 top-4 z-50 flex w-[min(360px,calc(100vw-2rem))] flex-col gap-2">
      {toasts.map((toast) => (
        <div
          className={`pointer-events-auto animate-fade-in rounded-xl border bg-white px-3.5 py-3 shadow-lg ${toastClass(toast.tone)}`}
          key={toast.id}
        >
          <div className="flex items-start gap-2.5">
            <div className="mt-0.5">{toastIcon(toast.tone)}</div>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold text-navy-900">{toast.title}</p>
              {toast.description ? (
                <p className="mt-0.5 text-xs leading-5 text-gray-500">{toast.description}</p>
              ) : null}
            </div>
            <Button
              aria-label="Закрыть уведомление"
              className="size-7 rounded-lg p-0 text-gray-400 hover:bg-gray-50 hover:text-gray-600"
              onClick={() => onDismiss(toast.id)}
              variant="ghost"
            >
              <X className="size-3.5" />
            </Button>
          </div>
        </div>
      ))}
    </div>
  )
}

function toastClass(tone: ToastTone): string {
  if (tone === 'success') {
    return 'border-emerald-100'
  }
  if (tone === 'error') {
    return 'border-red-100'
  }
  return 'border-navy-100'
}

function toastIcon(tone: ToastTone) {
  if (tone === 'success') {
    return <CheckCircle2 className="size-4 text-emerald-600" />
  }
  if (tone === 'error') {
    return <AlertTriangle className="size-4 text-red-500" />
  }
  return <Info className="size-4 text-navy-500" />
}
