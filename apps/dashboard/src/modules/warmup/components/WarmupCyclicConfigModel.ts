export type WarmupCycleDraft = {
  enabled: boolean
  startHour: number
  endHour: number
  daysTotal: number
}

export type WarmupCycleValidation = {
  isValid: boolean
  errors: Partial<Record<'startHour' | 'endHour' | 'daysTotal', string>>
}

export function validateWarmupCycleConfig(draft: WarmupCycleDraft): WarmupCycleValidation {
  if (!draft.enabled) return { errors: {}, isValid: true }

  const errors: WarmupCycleValidation['errors'] = {}
  if (draft.startHour < 0 || draft.startHour > 23) errors.startHour = 'Начало должно быть от 0 до 23.'
  if (draft.endHour < 0 || draft.endHour > 23) errors.endHour = 'Конец должен быть от 0 до 23.'
  if (draft.daysTotal < 1 || draft.daysTotal > 30) errors.daysTotal = 'Дней должно быть от 1 до 30.'
  if (draft.endHour <= draft.startHour) {
    errors.endHour = 'Конец должен быть позже начала. Ночные окна пока не поддерживаются.'
  } else if (draft.endHour - draft.startHour < 1) {
    errors.endHour = 'Минимум 1 час активного окна.'
  }

  return { errors, isValid: Object.keys(errors).length === 0 }
}

export function buildWarmupCyclePreview(draft: WarmupCycleDraft): string {
  if (!draft.enabled) return ''
  const hoursPerDay = Math.max(0, draft.endHour - draft.startHour)
  const totalActiveHours = hoursPerDay * draft.daysTotal
  return `Будет прогреваться ${draft.daysTotal} дней × ${hoursPerDay}ч = ${totalActiveHours}ч активности`
}
