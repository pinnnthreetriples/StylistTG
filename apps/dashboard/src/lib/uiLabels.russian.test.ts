import { describe, expect, it } from 'vitest'

import {
  labelRiskLevel,
  labelRiskLevelShort,
  labelRuntimeHealth,
  labelAccountState,
  labelProxyStatus,
  labelHealthDependency,
  labelRiskReason,
  runtimeHealthTone,
} from '@/lib/uiLabels'

describe('Russian label maps', () => {
  describe('labelRiskLevel', () => {
    it('maps low to Низкий риск', () => {
      expect(labelRiskLevel('low')).toBe('Низкий риск')
    })

    it('maps medium to Средний риск', () => {
      expect(labelRiskLevel('medium')).toBe('Средний риск')
    })

    it('maps high to Высокий риск', () => {
      expect(labelRiskLevel('high')).toBe('Высокий риск')
    })

    it('maps critical to Критический риск', () => {
      expect(labelRiskLevel('critical')).toBe('Критический риск')
    })
  })

  describe('labelRiskLevelShort', () => {
    it('maps low to Низкий', () => {
      expect(labelRiskLevelShort('low')).toBe('Низкий')
    })

    it('maps critical to Критический', () => {
      expect(labelRiskLevelShort('critical')).toBe('Критический')
    })
  })

  describe('labelRuntimeHealth', () => {
    it('maps ready to Готов', () => {
      expect(labelRuntimeHealth('ready')).toBe('Готов')
    })

    it('maps ok and ready to the same user-facing ready state', () => {
      expect(labelRuntimeHealth('ok')).toBe('Готов')
      expect(labelRuntimeHealth('ready')).toBe('Готов')
      expect(runtimeHealthTone('ok')).toBe('green')
      expect(runtimeHealthTone('ready')).toBe('green')
    })

    it('maps not_ready to Не готов', () => {
      expect(labelRuntimeHealth('not_ready')).toBe('Не готов')
    })

    it('maps timeout to Таймаут', () => {
      expect(labelRuntimeHealth('timeout')).toBe('Таймаут')
    })
  })

  describe('labelAccountState', () => {
    it('maps execution_usable to Готов к задачам', () => {
      expect(labelAccountState('execution_usable')).toBe('Готов к задачам')
    })

    it('maps reauth_required to Нужен повторный вход', () => {
      expect(labelAccountState('reauth_required')).toBe('Нужен повторный вход')
    })

    it('maps disabled to Отключён', () => {
      expect(labelAccountState('disabled')).toBe('Отключён')
    })
  })

  describe('labelProxyStatus', () => {
    it('maps none to Не назначен', () => {
      expect(labelProxyStatus('none')).toBe('Не назначен')
    })

    it('maps tcp_working to TCP работает', () => {
      expect(labelProxyStatus('tcp_working')).toBe('TCP работает')
    })

    it('maps failed to Ошибка подключения', () => {
      expect(labelProxyStatus('failed')).toBe('Ошибка подключения')
    })
  })

  describe('labelHealthDependency', () => {
    it('maps ok to Работает', () => {
      expect(labelHealthDependency('ok')).toBe('Работает')
    })

    it('maps not_configured to Не настроен', () => {
      expect(labelHealthDependency('not_configured')).toBe('Не настроен')
    })
  })

  describe('labelRiskReason', () => {
    it('maps reauth_required to Russian', () => {
      expect(labelRiskReason('reauth_required')).toBe('Нужна повторная авторизация')
    })

    it('maps missing_session to Russian', () => {
      expect(labelRiskReason('missing_session')).toBe('Сессия аккаунта не найдена')
    })

    it('maps runtime_unhealthy to Russian', () => {
      expect(labelRiskReason('runtime_unhealthy')).toBe('Среда аккаунта не готова')
    })

    it('falls back to errorLabels for known error codes', () => {
      expect(labelRiskReason('NETWORK_ERROR')).toBe('Нет связи с backend')
    })
  })

  describe('no raw enum leaks', () => {
    const rawEnums = ['ready', 'not_ready', 'execution_usable', 'disabled', 'low', 'medium', 'high', 'critical', 'none', 'failed']

    it('all raw enums have Russian mappings', () => {
      for (const raw of rawEnums) {
        const runtimeLabel = labelRuntimeHealth(raw)
        const riskLabel = labelRiskLevel(raw)
        const accountLabel = labelAccountState(raw)
        const proxyLabel = labelProxyStatus(raw)

        // At least one of these should have a non-passthrough Russian label
        const allLabels = [runtimeLabel, riskLabel, accountLabel, proxyLabel]
        const hasRussian = allLabels.some((label) => /[а-яА-Я]/.test(label))
        expect(hasRussian).toBe(true)
      }
    })
  })
})
