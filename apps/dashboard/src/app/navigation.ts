import { Activity, BriefcaseBusiness, CreditCard, HeartPulse, Network, Settings, Users } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

import { appRoutes } from '@/lib/routes'

export type NavigationItem = {
  label: string
  href: string
  icon: LucideIcon
  disabled?: boolean
}

export const primaryNavigation: NavigationItem[] = [
  { label: 'Accounts', href: appRoutes.accounts(), icon: Users },
  { label: 'Health Center', href: appRoutes.health(), icon: HeartPulse },
  { label: 'Jobs', href: appRoutes.jobs(), icon: Activity },
  { label: 'Proxy Center', href: appRoutes.proxy(), icon: Network },
  { label: 'Settings', href: appRoutes.settings(), icon: Settings },
  { label: 'Billing', href: '#billing-later', icon: CreditCard, disabled: true },
]

export const workspaceNavigation: NavigationItem[] = [
  { label: 'Operations', href: appRoutes.operations(), icon: BriefcaseBusiness },
]
