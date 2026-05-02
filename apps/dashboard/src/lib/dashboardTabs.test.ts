import { describe, expect, it } from 'vitest'

import { dashboardTabs, getDashboardTab, resolveDashboardTab } from '@/lib/dashboardTabs'

describe('dashboardTabs', () => {
  it('keeps profile as the safe default tab', () => {
    expect(resolveDashboardTab(null)).toBe('profile')
    expect(resolveDashboardTab('missing')).toBe('profile')
  })

  it('resolves known tab ids', () => {
    expect(resolveDashboardTab('tasks')).toBe('tasks')
    expect(getDashboardTab('overview').label).toBe('Обзор')
  })

  it('keeps stable tab order for the dashboard header', () => {
    expect(dashboardTabs.map((tab) => tab.id)).toEqual(['overview', 'profile', 'tasks', 'settings'])
  })
})
