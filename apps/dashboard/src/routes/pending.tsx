export function RoutePending() {
  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border bg-card">
        <div className="mx-auto flex h-14 max-w-5xl items-center px-5">
          <div className="h-4 w-28 rounded-full bg-muted" />
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-5 pt-5">
        <div className="rounded-xl border border-border bg-card p-6 text-sm text-muted-foreground shadow-sm">
          Загружаем раздел...
        </div>
      </main>
    </div>
  )
}
