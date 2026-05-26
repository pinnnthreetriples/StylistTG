import { useQuery } from '@tanstack/react-query'
import { ArrowLeft } from 'lucide-react'
import { Link } from '@tanstack/react-router'

import { compactOperationLogLabel } from '@/lib/operationLogs'
import { globalOperationLogsQueryOptions } from '@/lib/queries'
import { appRoutes } from '@/lib/routes'

export function OperationsRoute() {
  const logsQuery = useQuery(globalOperationLogsQueryOptions(100))
  const logs = logsQuery.data?.items ?? []

  return (
    <main className="min-h-screen bg-background px-4 py-8">
      <section className="mx-auto max-w-5xl rounded-xl border border-border bg-card p-4 shadow-sm">
        <div className="mb-4 flex items-center justify-between gap-3">
          <div>
            <h1 className="text-lg font-bold text-foreground">Журнал операций</h1>
            <p className="text-sm text-muted-foreground">Все проверки и действия по аккаунтам в одном месте.</p>
          </div>
          <Link className="inline-flex items-center gap-1 rounded-lg border border-border px-3 py-1.5 text-sm text-muted-foreground" to={appRoutes.accounts()}>
            <ArrowLeft className="size-4" />
            Аккаунты
          </Link>
        </div>
        {logsQuery.isLoading ? <p className="text-sm text-muted-foreground">Загружаем журнал…</p> : null}
        {!logsQuery.isLoading && logs.length === 0 ? (
          <p className="text-sm text-muted-foreground">Пока нет событий.</p>
        ) : (
          <div className="space-y-2">
            {logs.map((log) => (
              <article className="rounded-lg bg-muted px-3 py-2 text-sm" key={log.id}>
                <div className="flex items-center justify-between gap-3">
                  <span className="font-semibold text-foreground">{compactOperationLogLabel(log)}</span>
                  <span className="text-xs text-muted-foreground">{new Date(log.created_at).toLocaleString('ru-RU')}</span>
                </div>
                <p className="mt-1 text-xs text-muted-foreground">{log.message}</p>
              </article>
            ))}
          </div>
        )}
      </section>
    </main>
  )
}
