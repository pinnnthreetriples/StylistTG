import { describe, expect, it } from 'vitest'

import { primaryNavigation, workspaceNavigation } from '@/app/navigation'

describe('navigation', () => {
  it('renders Russian labels for all primary nav items', () => {
    const labels = primaryNavigation.map((item) => item.label)
    expect(labels).toContain('Аккаунты')
    expect(labels).toContain('Здоровье')
    expect(labels).toContain('Задачи')
    expect(labels).toContain('Комментарии')
    expect(labels).toContain('Настройки')
    expect(labels).toContain('Биллинг')
  })

  it('does not include Operations in primary navigation', () => {
    const labels = primaryNavigation.map((item) => item.label)
    expect(labels).not.toContain('Operations')
  })

  it('does not include Proxy Center in primary navigation', () => {
    const labels = primaryNavigation.map((item) => item.label)
    expect(labels).not.toContain('Proxy Center')
  })

  it('has Главная as the first nav item', () => {
    expect(primaryNavigation[0].label).toBe('Главная')
  })

  it('points Accounts primary navigation to the canonical accounts route', () => {
    const accounts = primaryNavigation.find((item) => item.label === 'Аккаунты')
    expect(accounts?.href).toBe('/accounts')
  })

  it('points NeuroCommenting navigation to the module route', () => {
    const item = primaryNavigation.find((entry) => entry.label === 'Комментарии')
    expect(item?.href).toBe('/modules/neuro-commenting')
  })

  it('has Биллинг as disabled', () => {
    const billing = primaryNavigation.find((item) => item.label === 'Биллинг')
    expect(billing).toBeDefined()
    expect(billing?.disabled).toBe(true)
  })

  it('does not include Operations in workspace navigation', () => {
    const labels = workspaceNavigation.map((item) => item.label)
    expect(labels).not.toContain('Operations')
  })

  it('workspace navigation is empty', () => {
    expect(workspaceNavigation).toHaveLength(0)
  })

  it('no primary nav items have English labels', () => {
    const englishPattern = /^[A-Z][a-z]+ [A-Z]/
    for (const item of primaryNavigation) {
      expect(item.label).not.toMatch(englishPattern)
    }
  })
})
