import { Badge, Tooltip } from '@stylisttg/ui'
import { Info } from 'lucide-react'

import type { WarmupActionCategory } from '../types'

// eslint-disable-next-line react-refresh/only-export-components
export const ACTION_CATEGORY_LABELS: Record<WarmupActionCategory, string> = {
  reading: 'Чтение',
  activity: 'Активность',
  entertainment: 'Развлечения',
  social: 'Социальные',
  groups: 'Группы',
  profile: 'Профиль/настройки',
}

export const TRAFFIC_TOOLTIP =
  'Эти действия активно используют трафик прокси. Отключайте на мобильных/резидентских прокси.'

export function ActionCategoryHeader({
  category,
  trafficHeavy,
}: {
  category: WarmupActionCategory
  trafficHeavy: boolean
}) {
  return (
    <div className="flex min-h-8 items-center justify-between gap-2 rounded-md border border-border bg-card px-3 py-2">
      <span className="text-sm font-semibold text-foreground">{ACTION_CATEGORY_LABELS[category]}</span>
      {trafficHeavy ? (
        <Tooltip content={TRAFFIC_TOOLTIP} side="bottom">
          <Badge className="gap-1" title={TRAFFIC_TOOLTIP} tone="amber">
            <Info className="size-3" />
            трафик
          </Badge>
        </Tooltip>
      ) : null}
    </div>
  )
}
