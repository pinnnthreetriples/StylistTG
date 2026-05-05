import type { ReactNode } from 'react'

import { cn } from './utils'

export type SidebarNavItem = {
  label: string
  href: string
  icon?: ReactNode
  disabled?: boolean
  badge?: ReactNode
}

export type SidebarNavProps = {
  items: SidebarNavItem[]
  activeHref: string
  onNavigate: (href: string) => void
  className?: string
}

export function SidebarNav({ items, activeHref, onNavigate, className }: SidebarNavProps) {
  return (
    <nav className={cn('grid gap-1', className)}>
      {items.map((item) => {
        const isActive = activeHref === item.href || (item.href !== '/' && activeHref.startsWith(`${item.href}/`))
        return (
          <button
            className={cn(
              'flex h-9 items-center gap-2.5 rounded-lg px-3 text-sm font-medium transition-all',
              isActive
                ? 'bg-gray-900/5 text-gray-900 font-semibold'
                : 'text-gray-500 hover:bg-gray-50 hover:text-gray-900',
              item.disabled && 'pointer-events-none opacity-45',
            )}
            disabled={item.disabled}
            key={item.href}
            onClick={() => onNavigate(item.href)}
            type="button"
          >
            {item.icon}
            <span className="truncate">{item.label}</span>
            {item.badge ? <span className="ml-auto">{item.badge}</span> : null}
          </button>
        )
      })}
    </nav>
  )
}
