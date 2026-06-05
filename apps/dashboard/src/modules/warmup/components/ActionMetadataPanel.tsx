import type { WarmupActionCategory, WarmupActionMetadata } from '../types'
import { ActionCategoryHeader } from './ActionCategoryHeader'

const CATEGORY_ORDER: WarmupActionCategory[] = [
  'reading',
  'activity',
  'entertainment',
  'social',
  'groups',
  'profile',
]

export function ActionMetadataPanel({ metadata }: { metadata: WarmupActionMetadata[] }) {
  if (metadata.length === 0) return null

  return (
    <div className="mt-3 grid gap-2 md:grid-cols-3">
      {CATEGORY_ORDER.map((category) => {
        const items = metadata.filter((item) => item.category === category)
        if (items.length === 0) return null
        return (
          <ActionCategoryHeader
            category={category}
            key={category}
            trafficHeavy={items.some((item) => item.traffic_heavy)}
          />
        )
      })}
    </div>
  )
}
