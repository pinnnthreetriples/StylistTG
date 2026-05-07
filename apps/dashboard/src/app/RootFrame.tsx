import { Outlet, useRouterState } from '@tanstack/react-router'

import { AppShell } from '@/app/AppShell'

export function RootFrame() {
  const pathname = useRouterState({ select: (state) => state.location.pathname })
  if (pathname === '/login') return <Outlet />
  return (
    <AppShell>
      <Outlet />
    </AppShell>
  )
}
