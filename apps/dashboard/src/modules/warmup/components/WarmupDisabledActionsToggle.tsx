import { Alert, Button, SectionCard } from '@stylisttg/ui'
import { RotateCcw, Save } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'

import { useUpdateWarmupDisabledActions } from '../hooks'
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

export function WarmupDisabledActionsToggle({
  sessionId,
  disabledActions,
  metadata,
  isMetadataLoading,
}: {
  sessionId: string
  disabledActions: string[]
  metadata: WarmupActionMetadata[]
  isMetadataLoading?: boolean
}) {
  const mutation = useUpdateWarmupDisabledActions()
  const grouped = useMemo(() => groupActionMetadata(metadata), [metadata])
  const [draft, setDraft] = useState<string[]>(() => normalizeDisabledActions(disabledActions, metadata))
  const normalizedSaved = useMemo(
    () => normalizeDisabledActions(disabledActions, metadata),
    [disabledActions, metadata],
  )
  const hasChanges = !sameActions(draft, normalizedSaved)
  const hasEnabledAction = hasAtLeastOneEnabled(metadata, draft)

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setDraft(normalizedSaved)
  }, [normalizedSaved])

  return (
    <SectionCard title="Отключённые действия" description="Текущая сессия">
      <div className="grid gap-3">
        {isMetadataLoading ? (
          <div className="rounded-md border border-border bg-muted px-3 py-2 text-sm text-muted-foreground">
            Загрузка действий
          </div>
        ) : null}
        {CATEGORY_ORDER.map((category) => {
          const items = grouped[category] ?? []
          if (items.length === 0) return null
          const trafficHeavy = items.some((item) => item.traffic_heavy)
          return (
            <div key={category} className="grid gap-2">
              <ActionCategoryHeader category={category} trafficHeavy={trafficHeavy} />
              <div className="grid gap-2 sm:grid-cols-2">
                {items.map((item) => (
                  <label
                    key={item.action_type}
                    className="flex min-h-10 items-center gap-2 rounded-md border border-border px-3 py-2 text-sm"
                  >
                    <input
                      checked={draft.includes(item.action_type)}
                      className="size-4"
                      type="checkbox"
                      onChange={(event) =>
                        setDraft(toggleAction(draft, item.action_type, event.target.checked))
                      }
                    />
                    <span className="min-w-0 flex-1 truncate">{formatActionLabel(item.action_type)}</span>
                  </label>
                ))}
              </div>
            </div>
          )
        })}
        {!hasEnabledAction ? (
          <Alert variant="error">Нужно оставить хотя бы одно действие включённым.</Alert>
        ) : null}
        {mutation.error ? (
          <Alert variant="error">Не удалось сохранить отключённые действия.</Alert>
        ) : null}
        <div className="flex flex-col gap-2 sm:flex-row">
          <Button
            disabled={!hasChanges || !hasEnabledAction || mutation.isPending}
            type="button"
            onClick={() => mutation.mutate({ sessionId, actions: draft })}
          >
            <Save className="size-4" />
            Сохранить
          </Button>
          <Button
            disabled={draft.length === 0 || mutation.isPending}
            type="button"
            variant="outline"
            onClick={() => setDraft([])}
          >
            <RotateCcw className="size-4" />
            Сброс
          </Button>
        </div>
      </div>
    </SectionCard>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function groupActionMetadata(metadata: WarmupActionMetadata[]) {
  return metadata.reduce(
    (groups, item) => {
      groups[item.category] = [...(groups[item.category] ?? []), item]
      return groups
    },
    {} as Partial<Record<WarmupActionCategory, WarmupActionMetadata[]>>,
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function normalizeDisabledActions(actions: string[], metadata: WarmupActionMetadata[]) {
  const requested = new Set(actions)
  return metadata.map((item) => item.action_type).filter((actionType) => requested.has(actionType))
}

// eslint-disable-next-line react-refresh/only-export-components
export function hasAtLeastOneEnabled(metadata: WarmupActionMetadata[], disabledActions: string[]) {
  const disabled = new Set(disabledActions)
  return metadata.some((item) => !disabled.has(item.action_type))
}

function toggleAction(actions: string[], actionType: string, checked: boolean) {
  if (checked) return actions.includes(actionType) ? actions : [...actions, actionType]
  return actions.filter((item) => item !== actionType)
}

function sameActions(left: string[], right: string[]) {
  return left.length === right.length && left.every((item, index) => item === right[index])
}

function formatActionLabel(actionType: string) {
  return actionType.replaceAll('_', ' ')
}
