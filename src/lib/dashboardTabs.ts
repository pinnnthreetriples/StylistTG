export type DashboardTabId = 'overview' | 'profile' | 'tasks' | 'settings'

export type DashboardTab = {
  id: DashboardTabId
  label: string
  title: string
  description: string
}

export const dashboardTabs = [
  {
    id: 'overview',
    label: 'Обзор',
    title: 'Обзор',
    description: 'Состояние аккаунта, runtime и последней задачи',
  },
  {
    id: 'profile',
    label: 'Профиль',
    title: 'Редактирование профиля',
    description: 'Измените профиль Telegram и создайте задачу для применения',
  },
  {
    id: 'tasks',
    label: 'Задачи',
    title: 'Задачи',
    description: 'План выполнения, результат и история запусков',
  },
  {
    id: 'settings',
    label: 'Настройки',
    title: 'Настройки',
    description: 'Runtime, диагностика и действия с текущей сессией',
  },
] as const satisfies readonly DashboardTab[]

export function resolveDashboardTab(value: string | null | undefined): DashboardTabId {
  return dashboardTabs.some((tab) => tab.id === value) ? (value as DashboardTabId) : 'profile'
}

export function getDashboardTab(tabId: DashboardTabId): DashboardTab {
  return dashboardTabs.find((tab) => tab.id === tabId) ?? dashboardTabs[1]
}
