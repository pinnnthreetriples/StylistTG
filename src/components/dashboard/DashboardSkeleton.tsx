import { Sparkles } from 'lucide-react'
import type { ReactNode } from 'react'

function SkeletonBlock({ className }: { className: string }) {
  return <div className={`skeleton-shimmer rounded-xl ${className}`} />
}

function SkeletonCard({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <section className={`rounded-2xl border border-gray-200/60 bg-white p-4 shadow-soft ${className}`}>
      {children}
    </section>
  )
}

export function DashboardSkeleton() {
  return (
    <div className="min-h-screen bg-cream text-navy-900 gradient-blob">
      <header className="border-b border-gray-200/60 bg-white">
        <div className="mx-auto max-w-[1400px] px-4 sm:px-6">
          <div className="flex h-14 items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="flex size-8 items-center justify-center rounded-lg bg-navy-400">
                <Sparkles className="size-4 text-white" />
              </div>
              <SkeletonBlock className="h-5 w-28" />
            </div>
            <SkeletonBlock className="hidden h-8 w-44 rounded-full sm:block" />
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-[1400px] px-4 py-6 sm:px-6">
        <div className="flex gap-6">
          <aside className="hidden w-72 shrink-0 flex-col gap-4 lg:flex">
            <SkeletonCard>
              <div className="flex items-center gap-3">
                <SkeletonBlock className="size-12 rounded-full" />
                <div className="flex-1 space-y-2">
                  <SkeletonBlock className="h-4 w-32" />
                  <SkeletonBlock className="h-3 w-24" />
                </div>
              </div>
              <SkeletonBlock className="mt-4 h-9 w-full" />
              <div className="mt-4 grid grid-cols-3 gap-2">
                <SkeletonBlock className="h-10" />
                <SkeletonBlock className="h-10" />
                <SkeletonBlock className="h-10" />
              </div>
            </SkeletonCard>
            <SkeletonCard>
              <SkeletonBlock className="h-5 w-28" />
              <SkeletonBlock className="mt-4 h-20 w-full" />
            </SkeletonCard>
            <SkeletonCard>
              <SkeletonBlock className="h-5 w-36" />
              <div className="mt-4 grid grid-cols-2 gap-2">
                <SkeletonBlock className="h-16" />
                <SkeletonBlock className="h-16" />
                <SkeletonBlock className="h-16" />
                <SkeletonBlock className="h-16" />
              </div>
            </SkeletonCard>
          </aside>

          <main className="min-w-0 flex-1 animate-fade-in">
            <div className="mb-6 flex items-center justify-between">
              <div className="space-y-2">
                <SkeletonBlock className="h-7 w-64" />
                <SkeletonBlock className="h-4 w-80 max-w-[70vw]" />
              </div>
              <SkeletonBlock className="hidden h-8 w-44 rounded-full sm:block" />
            </div>
            <section className="grid grid-cols-1 gap-6 xl:grid-cols-3">
              <SkeletonCard>
                <SkeletonBlock className="h-4 w-28" />
                <div className="mt-6 flex justify-center">
                  <SkeletonBlock className="size-28 rounded-full" />
                </div>
                <SkeletonBlock className="mt-5 h-28 w-full" />
                <SkeletonBlock className="mt-4 h-44 w-full" />
              </SkeletonCard>
              <div className="space-y-4 xl:col-span-2">
                <SkeletonCard>
                  <SkeletonBlock className="h-5 w-36" />
                  <div className="mt-5 grid gap-3 sm:grid-cols-2">
                    <SkeletonBlock className="h-11" />
                    <SkeletonBlock className="h-11" />
                  </div>
                </SkeletonCard>
                <SkeletonCard>
                  <SkeletonBlock className="h-5 w-32" />
                  <SkeletonBlock className="mt-5 h-11 w-full" />
                </SkeletonCard>
                <SkeletonCard>
                  <SkeletonBlock className="h-5 w-28" />
                  <SkeletonBlock className="mt-5 h-24 w-full" />
                </SkeletonCard>
                <SkeletonCard>
                  <div className="flex gap-3">
                    <SkeletonBlock className="h-12 flex-1" />
                    <SkeletonBlock className="h-12 w-32" />
                  </div>
                </SkeletonCard>
              </div>
            </section>
          </main>
        </div>
      </div>
    </div>
  )
}
