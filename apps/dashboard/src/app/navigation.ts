import { Activity, CreditCard, Flame, HeartPulse, Home, MessageSquareText, Settings, Users } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

import { appRoutes } from '@/lib/routes'

export type NavigationItem = {
  label: string
  href: string
  icon: LucideIcon
  disabled?: boolean
}

/**
 * Primary navigation — Accounts-first product structure.
 * Operations and Proxy Center are removed from main nav per product architecture.
 * - Operations → Settings → Расширенные → Журнал операций
 * - Proxy → inside individual account detail
 */
export const primaryNavigation: NavigationItem[] = [
  { label: 'Главная', href: '/home', icon: Home },
  { label: 'Аккаунты', href: appRoutes.accounts(), icon: Users },
  { label: 'Здоровье', href: appRoutes.health(), icon: HeartPulse },
  { label: 'Задачи', href: appRoutes.jobs(), icon: Activity },
  { label: 'Прогрев аккаунтов', href: appRoutes.warmup(), icon: Flame },
  { label: 'Комментарии', href: appRoutes.neuroCommenting(), icon: MessageSquareText },
  { label: 'Настройки', href: appRoutes.settings(), icon: Settings },
  { label: 'Биллинг', href: '/billing', icon: CreditCard, disabled: true },
]

/**
 * Workspace navigation is now empty.
 * Operations moved to Settings → Advanced.
 */
export const workspaceNavigation: NavigationItem[] = []
