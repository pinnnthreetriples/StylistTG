import { Link, useRouterState } from '@tanstack/react-router'
import { Badge, StatusPill } from '@stylisttg/ui'
import { Sparkles } from 'lucide-react'
import type { ReactNode } from 'react'

import { primaryNavigation, workspaceNavigation } from '@/app/navigation'

function normalizeEnvName(value: string | undefined): string {
  return value?.trim() || 'local'
}

function isActivePath(pathname: string, href: string): boolean {
  if (href === '/') return pathname === '/'
  return pathname === href || pathname.startsWith(`${href}/`)
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = useRouterState({ select: (state) => state.location.pathname })
  const appEnv = normalizeEnvName(import.meta.env.VITE_APP_ENV)
  const tdlibMode = appEnv === 'staging' ? 'mock/not_configured' : 'live-disabled'

  return (
    <div className="min-h-screen bg-cream text-navy-900">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 border-r border-gray-200/70 bg-white/95 px-4 py-4 shadow-sm xl:block">
        <div className="flex h-full flex-col">
          <div className="flex items-center gap-2 px-1">
            <div className="flex size-9 items-center justify-center rounded-lg bg-navy-400 text-white">
              <Sparkles className="size-4" />
            </div>
            <div>
              <div className="font-display text-base font-bold">StylistTG</div>
              <div className="text-[11px] font-medium text-gray-400">SaaS workspace</div>
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

          <div className="mt-auto grid gap-1.5">
            {workspaceNavigation.map((item) => {
              const Icon = item.icon
              const active = isActivePath(pathname, item.href)
              return (
                <Link
                  className={`flex h-10 items-center gap-2 rounded-lg px-3 text-sm font-semibold transition-all ${
                    active ? 'bg-navy-50 text-navy-900' : 'text-gray-500 hover:bg-gray-50 hover:text-navy-900'
                  }`}
                  key={item.label}
                  to={item.href}
                >
                  <Icon className="size-4" />
                  {item.label}
                </Link>
              )
            })}
          </div>
        </div>
      </aside>

      <div className="min-h-screen xl:pl-64">
        <header className="sticky top-0 z-20 border-b border-gray-200/70 bg-white/90 backdrop-blur">
          <div className="mx-auto flex h-14 max-w-6xl items-center gap-3 px-4 sm:px-6">
            <div className="flex min-w-0 flex-1 items-center gap-2">
              <span className="truncate text-sm font-bold text-navy-900">Workspace: Staging Ops</span>
              <Badge tone={appEnv === 'staging' ? 'blue' : 'gray'}>{appEnv}</Badge>
            </div>
            <StatusPill tone="amber">TDLib {tdlibMode}</StatusPill>
          </div>
          <nav className="flex gap-1 overflow-x-auto px-4 pb-2 xl:hidden">
            {primaryNavigation
              .filter((item) => !item.disabled)
              .map((item) => (
                <Link
                  className={`shrink-0 rounded-lg px-3 py-1.5 text-xs font-semibold ${
                    isActivePath(pathname, item.href) ? 'bg-navy-50 text-navy-900' : 'text-gray-500'
                  }`}
                  key={item.label}
                  to={item.href}
                >
                  {item.label}
                </Link>
              ))}
          </nav>
        </header>
        <main>{children}</main>
      </div>
    </div>
  )
}
