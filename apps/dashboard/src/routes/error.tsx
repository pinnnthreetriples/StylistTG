import { useRouter } from '@tanstack/react-router'
import { ArrowLeft, RefreshCw } from 'lucide-react'

import { normalizeError } from '@/lib/appErrors'
import { labelIssue } from '@/lib/uiLabels'

export function RouteError({ error, reset }: { error: unknown; reset: () => void }) {
  const router = useRouter()
  const normalized = normalizeError(error)

  function retry() {
    reset()
    void router.invalidate()
  }

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border bg-card">
        <div className="mx-auto flex h-14 max-w-5xl items-center px-5">
          <div className="font-sans text-base font-bold tracking-tight text-foreground">StylistTG</div>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-5 pt-6">
        <section className="rounded-xl border border-border bg-card p-5 shadow-sm">
          <div className="max-w-2xl">
            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Раздел не загрузился</p>
            <h1 className="mt-2 text-lg font-bold text-foreground">{labelIssue(normalized.error_code)}</h1>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              Данные этого раздела сейчас недоступны. Проверьте backend и попробуйте снова.
            </p>

            <div className="mt-4 flex flex-wrap gap-2">
              <button
                className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground transition hover:bg-primary"
                onClick={retry}
                type="button"
              >
                <RefreshCw className="size-4" />
                Повторить
              </button>
              <button
                className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-2 text-sm font-semibold text-muted-foreground transition hover:bg-muted"
                onClick={() => {
                  reset()
                  if (router.history.canGoBack()) {
                    router.history.back()
                  } else {
                    void router.navigate({ href: '/' })
                  }
                }}
                type="button"
              >
                <ArrowLeft className="size-4" />
                Назад
              </button>
            </div>

            <details className="mt-5 rounded-lg border border-border bg-muted px-3 py-2">
              <summary className="cursor-pointer text-xs font-semibold text-muted-foreground">
                Технические детали
              </summary>
              <dl className="mt-3 grid gap-2 text-xs text-muted-foreground sm:grid-cols-2">
                <div>
                  <dt className="font-semibold text-muted-foreground">Код</dt>
                  <dd className="break-all">{normalized.error_code}</dd>
                </div>
                <div>
                  <dt className="font-semibold text-muted-foreground">Класс</dt>
                  <dd className="break-all">{normalized.error_class}</dd>
                </div>
                <div>
                  <dt className="font-semibold text-muted-foreground">Request ID</dt>
                  <dd className="break-all">{normalized.request_id}</dd>
                </div>
                <div className="sm:col-span-2">
                  <dt className="font-semibold text-muted-foreground">Сообщение</dt>
                  <dd className="break-all">{normalized.message}</dd>
                </div>
              </dl>
            </details>
          </div>
        </section>
      </main>
    </div>
  )
}
