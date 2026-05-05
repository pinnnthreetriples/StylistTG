import { Link, useRouterState } from '@tanstack/react-router'
import { Badge, StatusPill } from '@stylisttg/ui'
import { Menu, Sparkles, X } from 'lucide-react'
import { useState, type ReactNode } from 'react'

import { primaryNavigation } from '@/app/navigation'

function normalizeEnvName(value: string | undefined): string {
  const env = value?.trim() || 'local'
  if (env === 'local') return 'Локальная среда'
  if (env === 'staging') return 'Staging'
  return env
}

function isActivePath(pathname: string, href: string): boolean {
  if (href === '/') return pathname === '/'
  return pathname === href || pathname.startsWith(`${href}/`)
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = useRouterState({ select: (state) => state.location.pathname })
  const appEnv = normalizeEnvName(import.meta.env.VITE_APP_ENV)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  return (
    <div className="min-h-screen bg-cream text-navy-900">
      {/* Desktop Sidebar */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 border-r border-gray-200/70 bg-white/95 px-4 py-4 shadow-sm xl:block">
        <div className="flex h-full flex-col">
          <div className="flex items-center gap-2 px-1">
            <div className="flex size-9 items-center justify-center rounded-lg bg-navy-400 text-white">
              <Sparkles className="size-4" />
            </div>
            <div>
              <div className="font-display text-base font-bold">StylistTG</div>
              <div className="text-[11px] font-medium text-gray-400">Рабочая область</div>
            </div>
          </div>

          <nav className="mt-6 grid gap-1.5">
            {primaryNavigation.map((item) => {
              const Icon = item.icon
              const active = !item.disabled && isActivePath(pathname, item.href)
              const className = `flex h-10 items-center gap-2 rounded-lg px-3 text-sm font-semibold transition-all ${
                active ? 'bg-navy-50 text-navy-900' : 'text-gray-500 hover:bg-gray-50 hover:text-navy-900'
              } ${item.disabled ? 'pointer-events-none opacity-45' : ''}`

              return item.disabled ? (
                <span className={className} key={item.label}>
                  <Icon className="size-4" />
                  {item.label}
                </span>
              ) : (
                <Link className={className} key={item.label} to={item.href}>
                  <Icon className="size-4" />
                  {item.label}
                </Link>
              )
            })}
          </nav>

          {/* Bottom section: environment info */}
          <div className="mt-auto space-y-2 px-1">
            <StatusPill tone="amber">TDLib отключён безопасно</StatusPill>
            <div className="flex items-center gap-1.5">
              <Badge tone={appEnv === 'staging' ? 'blue' : 'gray'}>{appEnv}</Badge>
            </div>
          </div>
        </div>
      </aside>

      <div className="min-h-screen xl:pl-64">
        {/* Top bar */}
        <header className="sticky top-0 z-20 border-b border-gray-200/70 bg-white/90 backdrop-blur">
          <div className="mx-auto flex h-14 max-w-6xl items-center gap-3 px-4 sm:px-6">
            <button
              aria-label="Открыть меню"
              className="flex size-9 items-center justify-center rounded-lg text-gray-500 transition hover:bg-gray-50 xl:hidden"
              onClick={() => setMobileMenuOpen(true)}
              type="button"
            >
              <Menu className="size-5" />
            </button>
            <div className="flex min-w-0 flex-1 items-center gap-2">
              <span className="truncate text-sm font-bold text-navy-900">Рабочая область</span>
              <Badge tone={appEnv === 'staging' ? 'blue' : 'gray'}>{appEnv}</Badge>
            </div>
            <StatusPill tone="amber">TDLib отключён</StatusPill>
          </div>
        </header>

        <main>{children}</main>
      </div>

      {/* Mobile sidebar overlay */}
      {mobileMenuOpen ? (
        <div className="fixed inset-0 z-40 xl:hidden">
          <div
            aria-hidden
            className="fixed inset-0 bg-black/30 backdrop-blur-sm"
            onClick={() => setMobileMenuOpen(false)}
          />
          <aside className="fixed inset-y-0 left-0 z-50 w-72 border-r border-gray-200 bg-white px-4 py-4 shadow-xl animate-[fade-in_0.15s_ease-out_both]">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="flex size-8 items-center justify-center rounded-lg bg-navy-400 text-white">
                  <Sparkles className="size-3.5" />
                </div>
                <span className="font-display text-sm font-bold">StylistTG</span>
              </div>
              <button
                aria-label="Закрыть меню"
                className="flex size-8 items-center justify-center rounded-lg text-gray-400 hover:bg-gray-50"
                onClick={() => setMobileMenuOpen(false)}
                type="button"
              >
                <X className="size-4" />
              </button>
            </div>
            <nav className="mt-5 grid gap-1">
              {primaryNavigation
                .map((item) => {
                  const Icon = item.icon
                  const className = `flex h-10 items-center gap-2 rounded-lg px-3 text-sm font-semibold transition-all ${
                    !item.disabled && isActivePath(pathname, item.href) ? 'bg-navy-50 text-navy-900' : 'text-gray-500'
                  } ${item.disabled ? 'pointer-events-none opacity-45' : ''}`
                  return item.disabled ? (
                    <span className={className} key={item.label}>
                      <Icon className="size-4" />
                      {item.label}
                    </span>
                  ) : (
                    <Link
                      className={className}
                      key={item.label}
                      onClick={() => setMobileMenuOpen(false)}
                      to={item.href}
                    >
                      <Icon className="size-4" />
                      {item.label}
                    </Link>
                  )
                })}
            </nav>
          </aside>
        </div>
      ) : null}
    </div>
  )
}
