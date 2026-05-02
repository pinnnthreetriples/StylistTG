export function RoutePending() {
  return (
    <div className="min-h-screen bg-cream">
      <header className="border-b border-gray-200/70 bg-white">
        <div className="mx-auto flex h-14 max-w-5xl items-center px-5">
          <div className="h-4 w-28 rounded-full bg-gray-100" />
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-5 pt-5">
        <div className="rounded-xl border border-gray-200/70 bg-white p-6 text-sm text-gray-500 shadow-sm">
          Загружаем раздел...
        </div>
      </main>
    </div>
  )
}
