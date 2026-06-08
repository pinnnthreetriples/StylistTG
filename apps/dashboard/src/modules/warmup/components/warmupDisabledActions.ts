import type { WarmupActionCategory, WarmupActionMetadata } from '../types'

export function groupActionMetadata(metadata: WarmupActionMetadata[]) {
  return metadata.reduce(
    (groups, item) => {
      groups[item.category] = [...(groups[item.category] ?? []), item]
      return groups
    },
    {} as Partial<Record<WarmupActionCategory, WarmupActionMetadata[]>>,
  )
}

export function normalizeDisabledActions(actions: string[], metadata: WarmupActionMetadata[]) {
  const requested = new Set(actions)
  return metadata.map((item) => item.action_type).filter((actionType) => requested.has(actionType))
}

export function hasAtLeastOneEnabled(metadata: WarmupActionMetadata[], disabledActions: string[]) {
  const disabled = new Set(disabledActions)
  return metadata.some((item) => !disabled.has(item.action_type))
}
