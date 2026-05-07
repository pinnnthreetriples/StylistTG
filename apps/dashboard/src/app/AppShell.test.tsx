import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, test } from 'vitest'

import { primaryNavigation } from '@/app/navigation'

describe('SaaS shell navigation', () => {
  test('defines the expected product zones', () => {
    expect(primaryNavigation.map((item) => item.label)).toEqual([
      'Главная',
      'Аккаунты',
      'Здоровье',
      'Задачи',
      'Прогрев аккаунтов',
      'Настройки',
      'Биллинг',
    ])
  })

  test('can render simple shell content without a browser', () => {
    const html = renderToStaticMarkup(<div data-shell="saas">Рабочая область</div>)

    expect(html).toContain('Рабочая область')
  })
})
