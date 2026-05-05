import { createContext, useContext, type ReactNode } from 'react'

import { cn } from './utils'

type TabsContextValue = {
  value: string
  onValueChange: (value: string) => void
}

const TabsContext = createContext<TabsContextValue | null>(null)

function useTabsContext(): TabsContextValue {
  const ctx = useContext(TabsContext)
  if (!ctx) throw new Error('Tabs components must be used within <Tabs>')
  return ctx
}

export type TabsProps = {
  value: string
  onValueChange: (value: string) => void
  children: ReactNode
  className?: string
}

export function Tabs({ value, onValueChange, children, className }: TabsProps) {
  return (
    <TabsContext.Provider value={{ value, onValueChange }}>
      <div className={className}>{children}</div>
    </TabsContext.Provider>
  )
}

export function TabsList({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div
      className={cn(
        'inline-flex items-center gap-1 rounded-lg bg-gray-100/80 p-1',
        className,
      )}
      role="tablist"
    >
      {children}
    </div>
  )
}

export type TabsTriggerProps = {
  value: string
  children: ReactNode
  className?: string
  disabled?: boolean
}

export function TabsTrigger({ value, children, className, disabled }: TabsTriggerProps) {
  const { value: activeValue, onValueChange } = useTabsContext()
  const isActive = activeValue === value

  return (
    <button
      aria-selected={isActive}
      className={cn(
        'inline-flex items-center justify-center rounded-md px-3 py-1.5 text-sm font-medium transition-all',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-navy-400',
        isActive
          ? 'bg-white text-navy-900 shadow-sm'
          : 'text-gray-500 hover:text-gray-900',
        disabled && 'pointer-events-none opacity-50',
        className,
      )}
      disabled={disabled}
      onClick={() => onValueChange(value)}
      role="tab"
      type="button"
    >
      {children}
    </button>
  )
}

export function TabsContent({
  value,
  children,
  className,
}: {
  value: string
  children: ReactNode
  className?: string
}) {
  const { value: activeValue } = useTabsContext()
  if (activeValue !== value) return null
  return (
    <div className={className} role="tabpanel">
      {children}
    </div>
  )
}
