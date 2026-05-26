import { Link, useNavigate, useRouterState } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { Badge, StatusPill } from '@stylisttg/ui'
import { LogOut, Menu, Sparkles, X } from 'lucide-react'
import { useState, type ReactNode } from 'react'

import { primaryNavigation } from '@/app/navigation'
import { useSupabaseAuth } from '@/features/auth/SupabaseAuthContext'
import { DisasterModeBanner } from '@/features/home/DisasterModeBanner'
import { useCurrentUser } from '@/hooks/queries/useCurrentUser'
import { getLiveStatus } from '@/lib/liveStatus'
import { frontendDiagnosticsQueryOptions, workerDiagnosticsQueryOptions } from '@/lib/queries'

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
  const navigate = useNavigate()
  const appEnv = normalizeEnvName(import.meta.env.VITE_APP_ENV)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const { signOut } = useSupabaseAuth()
  const currentUserQuery = useCurrentUser()
  const diagnosticsQuery = useQuery(frontendDiagnosticsQueryOptions())
  const workerDiagnosticsQuery = useQuery(workerDiagnosticsQueryOptions())
  const currentUser = currentUserQuery.data
  const workspaceLabel = currentUser?.workspace_name ?? 'Рабочая область'
  const liveStatus = getLiveStatus(diagnosticsQuery.data, workerDiagnosticsQuery.data)
  const handleSignOut = async () => {
    await signOut()
    void navigate({ to: '/login', replace: true })
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      {/* Desktop Sidebar */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 border-r border-border bg-card/95 px-4 py-4 shadow-sm xl:block">
        <div className="flex h-full flex-col">
          <div className="flex items-center gap-2 px-1">
            <div className="flex size-9 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <Sparkles className="size-4" />
            </div>
            <div>
              <div className="font-sans text-base font-bold">StylistTG</div>
              <div className="text-[11px] font-medium text-muted-foreground">{workspaceLabel}</div>
            </div>
          </div>

          <nav className="mt-6 grid gap-1.5">
            {primaryNavigation.map((item) => {
              const Icon = item.icon
              const active = !item.disabled && isActivePath(pathname, item.href)
              const className = `flex h-10 items-center gap-2 rounded-lg px-3 text-sm font-semibold transition-all ${
                active ? 'bg-muted text-foreground' : 'text-muted-foreground hover:bg-muted hover:text-foreground'
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
            <StatusPill tone={liveStatus.tone}>{liveStatus.label}</StatusPill>
            <button
              className="flex h-9 w-full items-center gap-2 rounded-lg px-3 text-sm font-semibold text-muted-foreground transition hover:bg-muted hover:text-foreground"
              onClick={() => void handleSignOut()}
              type="button"
            >
              <LogOut className="size-4" />
              Выход
            </button>
            <div className="flex items-center gap-1.5">
              <Badge tone={appEnv === 'staging' ? 'blue' : 'gray'}>{appEnv}</Badge>
            </div>
          </div>
        </div>
      </aside>

      <div className="min-h-screen xl:pl-64">
        {/* Top bar */}
        <header className="sticky top-0 z-20 border-b border-border bg-card/90 backdrop-blur">
          <div className="mx-auto flex h-14 max-w-6xl items-center gap-3 px-4 sm:px-6">
            <button
              aria-label="Открыть меню"
              className="flex size-9 items-center justify-center rounded-lg text-muted-foreground transition hover:bg-muted xl:hidden"
              onClick={() => setMobileMenuOpen(true)}
              type="button"
            >
              <Menu className="size-5" />
            </button>
            <div className="flex min-w-0 flex-1 items-center gap-2">
              <span className="truncate text-sm font-bold text-foreground">{workspaceLabel}</span>
              <Badge tone={appEnv === 'staging' ? 'blue' : 'gray'}>{appEnv}</Badge>
            </div>
            <StatusPill tone={liveStatus.tone}>{liveStatus.label}</StatusPill>
            <button
              className="hidden h-9 items-center gap-2 rounded-lg px-3 text-sm font-semibold text-muted-foreground transition hover:bg-muted hover:text-foreground sm:flex"
              onClick={() => void handleSignOut()}
              type="button"
            >
              <LogOut className="size-4" />
              Выход
            </button>
          </div>
        </header>

        <DisasterModeBanner />
        <main>{children}</main>
      </div>

      {/* Mobile sidebar overlay */}
      {mobileMenuOpen ? (
        <div className="fixed inset-0 z-40 xl:hidden">
          <div
            aria-hidden
            className="fixed inset-0 bg-foreground/30 backdrop-blur-sm"
            onClick={() => setMobileMenuOpen(false)}
          />
          <aside className="fixed inset-y-0 left-0 z-50 w-72 border-r border-border bg-card px-4 py-4 shadow-xl">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
                  <Sparkles className="size-3.5" />
                </div>
                <span className="font-sans text-sm font-bold">StylistTG</span>
              </div>
              <button
                aria-label="Закрыть меню"
                className="flex size-8 items-center justify-center rounded-lg text-muted-foreground hover:bg-muted"
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
                    !item.disabled && isActivePath(pathname, item.href) ? 'bg-muted text-foreground' : 'text-muted-foreground'
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
