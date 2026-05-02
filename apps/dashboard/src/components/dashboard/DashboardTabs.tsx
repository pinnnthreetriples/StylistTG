import { type ReactNode } from 'react'

import { dashboardTabs, type DashboardTabId } from '@/lib/dashboardTabs'

export function DashboardTabs({
  activeTab,
  onChange,
}: {
  activeTab: DashboardTabId
  onChange: (tabId: DashboardTabId) => void
}) {
  return (
    <nav aria-label="Разделы панели" className="hidden items-center gap-1 md:flex" role="tablist">
      {dashboardTabs.map((tab) => {
        const active = tab.id === activeTab

        return (
          <button
            aria-controls={`dashboard-panel-${tab.id}`}
            aria-selected={active}
            className={
              active
                ? 'rounded-lg bg-navy-50 px-3.5 py-1.5 text-sm font-medium text-navy-400'
                : 'rounded-lg px-3.5 py-1.5 text-sm font-medium text-gray-500 transition-colors hover:bg-gray-100/60 hover:text-gray-800'
            }
            id={`dashboard-tab-${tab.id}`}
            key={tab.id}
            onClick={() => onChange(tab.id)}
            role="tab"
            type="button"
          >
            {tab.label}
          </button>
        )
      })}
    </nav>
  )
}

export function DashboardTabPanel({
  activeTab,
  children,
  tabId,
}: {
  activeTab: DashboardTabId
  children: ReactNode
  tabId: DashboardTabId
}) {
  const active = activeTab === tabId

  return (
    <section
      aria-labelledby={`dashboard-tab-${tabId}`}
      className={active ? undefined : 'hidden'}
      hidden={!active}
      id={`dashboard-panel-${tabId}`}
      role="tabpanel"
    >
      {children}
    </section>
  )
}
