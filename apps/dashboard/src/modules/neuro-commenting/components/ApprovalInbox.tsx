import { Card } from '@stylisttg/ui'
import { useEffect, useMemo, useRef, useState } from 'react'

import { useGeneratedCommentMutations, useNeuroGeneratedComments } from '../hooks'
import { ApprovalBadge } from './ApprovalBadge'

/**
 * Phase 0 Task 4 keyboard-driven approval queue.
 *
 * Keyboard shortcuts (handled only while this component is mounted and the
 * focus is not inside an editable field):
 *
 *   j / ArrowDown - next comment
 *   k / ArrowUp   - previous comment
 *   a             - approve focused comment
 *   r             - reject focused comment (with default reason)
 *   e             - start editing focused comment
 *   s             - skip (advance without action)
 *   ?             - show shortcuts hint
 */

type Pending = { id: string; text: string; status: string; campaignId: string }

const SHORTCUTS_LABEL =
  'j/k навигация · a одобрить · r отклонить · e редактировать · s пропустить · ? справка'

export function ApprovalInbox({
  campaignId,
}: {
  campaignId: string
}) {
  const commentsQuery = useNeuroGeneratedComments(campaignId)
  const mutations = useGeneratedCommentMutations(campaignId)
  const containerRef = useRef<HTMLDivElement | null>(null)
  const [rawActiveIndex, setActiveIndex] = useState(0)
  const [showHint, setShowHint] = useState(false)
  const [statusMessage, setStatusMessage] = useState<string | null>(null)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editText, setEditText] = useState('')

  const commentItems = commentsQuery.data?.items
  const pending: Pending[] = useMemo(
    () =>
      (commentItems ?? [])
        .filter((comment) => comment.approval_status === 'pending' || comment.approval_status === 'edited')
        .map((comment) => ({
          id: comment.id,
          text: comment.edited_text ?? comment.final_text ?? comment.generated_text,
          status: comment.approval_status,
          campaignId: comment.campaign_id,
        })),
    [commentItems],
  )

  // Derived in render to avoid setState in effect; the queue length can shrink
  // when items move out of pending status and the previously-focused index
  // would otherwise point past the end.
  const activeIndex = pending.length === 0 ? 0 : Math.min(rawActiveIndex, pending.length - 1)

  useEffect(() => {
    function isEditableTarget(target: EventTarget | null): boolean {
      if (!(target instanceof HTMLElement)) return false
      const tag = target.tagName.toLowerCase()
      if (tag === 'input' || tag === 'textarea' || tag === 'select') return true
      if (target.isContentEditable) return true
      return false
    }

    function handler(event: KeyboardEvent) {
      if (event.metaKey || event.ctrlKey || event.altKey) return
      if (isEditableTarget(event.target)) return
      if (pending.length === 0 && event.key !== '?') return
      const active = pending[activeIndex]

      switch (event.key) {
        case 'j':
        case 'ArrowDown':
          event.preventDefault()
          setActiveIndex((idx) => Math.min(idx + 1, Math.max(0, pending.length - 1)))
          break
        case 'k':
        case 'ArrowUp':
          event.preventDefault()
          setActiveIndex((idx) => Math.max(0, idx - 1))
          break
        case 'a':
          if (!active) return
          event.preventDefault()
          mutations.approve.mutate(active.id)
          setStatusMessage('approve sent')
          break
        case 'r':
          if (!active) return
          event.preventDefault()
          mutations.reject.mutate({
            commentId: active.id,
            payload: { reason: 'rejected via keyboard shortcut' },
          })
          setStatusMessage('reject sent')
          break
        case 'e':
          if (!active) return
          event.preventDefault()
          setEditingId(active.id)
          setEditText(active.text)
          break
        case 's':
          if (!active) return
          event.preventDefault()
          setActiveIndex((idx) => Math.min(idx + 1, Math.max(0, pending.length - 1)))
          setStatusMessage('skipped')
          break
        case '?':
          event.preventDefault()
          setShowHint((value) => !value)
          break
      }
    }

    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [pending, activeIndex, mutations.approve, mutations.reject])

  const submitEdit = () => {
    if (!editingId) return
    const trimmed = editText.trim()
    if (!trimmed) return
    mutations.edit.mutate({ commentId: editingId, payload: { edited_text: trimmed } })
    setEditingId(null)
    setEditText('')
  }

  return (
    <Card className="p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-foreground">
          Очередь модерации ({pending.length})
        </h3>
        <button
          type="button"
          className="text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
          onClick={() => setShowHint((value) => !value)}
        >
          ? горячие клавиши
        </button>
      </div>
      {showHint ? (
        <p className="mb-3 rounded-md bg-muted px-3 py-2 text-xs text-muted-foreground">{SHORTCUTS_LABEL}</p>
      ) : null}
      {commentsQuery.isError ? (
        <p className="text-sm text-destructive">Не удалось загрузить данные</p>
      ) : null}
      {!commentsQuery.isLoading && pending.length === 0 ? (
        <p className="text-sm text-muted-foreground">Все комментарии обработаны.</p>
      ) : null}
      <div ref={containerRef} className="space-y-2">
        {pending.map((comment, index) => {
          const isActive = index === activeIndex
          const isEditing = editingId === comment.id
          return (
            <div
              key={comment.id}
              className={`rounded-lg border p-3 transition ${
                isActive ? 'border-border bg-muted' : 'border-border bg-muted'
              }`}
            >
              <div className="mb-2 flex items-start justify-between gap-2">
                {isEditing ? (
                  <textarea
                    aria-label="Текст комментария"
                    className="min-h-20 flex-1 rounded-md border border-border bg-card px-3 py-2 text-sm focus:border-border focus:outline-none focus:ring-2 focus:ring-ring"
                    value={editText}
                    onChange={(event) => setEditText(event.target.value)}
                  />
                ) : (
                  <p className="text-sm text-foreground">{comment.text}</p>
                )}
                <ApprovalBadge status={comment.status} />
              </div>
              {isEditing ? (
                <div className="flex gap-2">
                  <button
                    type="button"
                    className="rounded-md border border-border bg-muted px-2 py-1 text-xs font-medium text-foreground hover:bg-muted"
                    onClick={submitEdit}
                  >
                    Сохранить
                  </button>
                  <button
                    type="button"
                    className="rounded-md border border-border bg-card px-2 py-1 text-xs text-muted-foreground hover:bg-muted"
                    onClick={() => {
                      setEditingId(null)
                      setEditText('')
                    }}
                  >
                    Отмена
                  </button>
                </div>
              ) : null}
            </div>
          )
        })}
      </div>
      {statusMessage ? (
        <p className="mt-3 text-xs text-muted-foreground" aria-live="polite">
          {statusMessage}
        </p>
      ) : null}
    </Card>
  )
}
