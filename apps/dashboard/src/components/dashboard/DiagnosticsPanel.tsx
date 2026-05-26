import { RefreshCw, Server } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { buildDiagnosticItems } from '@/lib/diagnostics'

export function DiagnosticsPanel({
  items,
  isRefreshing,
  onRefresh,
}: {
  items: ReturnType<typeof buildDiagnosticItems>
  isRefreshing: boolean
  onRefresh: () => void
}) {
  return (
    <section className="rounded-2xl border border-border bg-card p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2">
          <div className="flex size-7 flex-shrink-0 items-center justify-center rounded-lg bg-muted">
            <Server className="size-3.5 text-primary" />
          </div>
          <div className="min-w-0">
            <h3 className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Система</h3>
            <p className="truncate text-[10px] text-muted-foreground">DB, Redis, TDLib и runtime</p>
          </div>
        </div>
        <Button
          aria-label="Обновить диагностику"
          className="size-8 flex-shrink-0 rounded-lg bg-muted p-0 text-muted-foreground hover:bg-muted"
          onClick={onRefresh}
          variant="ghost"
        >
          <RefreshCw className={`size-3.5 ${isRefreshing ? 'animate-spin' : ''}`} />
        </Button>
      </div>
      <div className="space-y-1.5">
        {items.length === 0 ? (
          <div className="rounded-xl bg-muted px-3 py-2 text-xs text-muted-foreground">Диагностика загружается</div>
        ) : (
          items.map((item) => (
            <div className="flex items-center justify-between gap-3 rounded-xl bg-muted px-3 py-2" key={item.key}>
              <span className="min-w-0 truncate text-xs font-medium text-muted-foreground">{item.label}</span>
              <span className={`flex items-center gap-1.5 text-[10px] font-semibold ${diagnosticTextClass(item.status)}`}>
                <span className={`size-1.5 rounded-full ${diagnosticDotClass(item.status)}`} />
                <span className="max-w-28 truncate">{item.message}</span>
              </span>
            </div>
          ))
        )}
      </div>
    </section>
  )
}

function diagnosticDotClass(status: 'ok' | 'down' | 'attention'): string {
  if (status === 'ok') {
    return 'bg-muted'
  }
  if (status === 'down') {
    return 'bg-destructive'
  }
  return 'bg-muted'
}

function diagnosticTextClass(status: 'ok' | 'down' | 'attention'): string {
  if (status === 'ok') {
    return 'text-primary'
  }
  if (status === 'down') {
    return 'text-destructive'
  }
  return 'text-muted-foreground'
}
