import { Button, Card, EmptyState, Skeleton } from '@stylisttg/ui'
import { Check, Pencil, Save, X } from 'lucide-react'
import { useState } from 'react'

import { buildGeneratedCommentEditPayload, visibleGeneratedCommentText } from '../formPayloads'
import { useGeneratedCommentMutations, useNeuroGeneratedComments } from '../hooks'
import type { NeuroGeneratedCommentUpdate } from '../types'

import { ApprovalBadge } from './ApprovalBadge'

export function GeneratedCommentsSection({ campaignId }: { campaignId: string | undefined }) {
  const commentsQuery = useNeuroGeneratedComments(campaignId)
  const mutations = useGeneratedCommentMutations(campaignId)
  const [editingCommentId, setEditingCommentId] = useState<string | null>(null)
  const [editedText, setEditedText] = useState('')
  const [rejectReason, setRejectReason] = useState('')
  const [formError, setFormError] = useState<string | null>(null)
  const comments = commentsQuery.data?.items ?? []

  if (commentsQuery.isError) {
    return <Card className="p-4 text-sm text-red-600">Не удалось загрузить данные</Card>
  }
  if (commentsQuery.isLoading) return <Skeleton className="h-40 w-full" />

  const isMutating = mutations.edit.isPending || mutations.approve.isPending || mutations.reject.isPending
  const mutationError =
    mutations.edit.isError || mutations.approve.isError || mutations.reject.isError
      ? 'Не удалось сохранить изменения'
      : null

  return (
    <Card className="p-4">
      <h3 className="mb-3 text-sm font-semibold text-gray-900">
        Сгенерированные комментарии ({commentsQuery.data?.total ?? 0})
      </h3>
      {comments.length === 0 ? (
        <EmptyState title="Нет комментариев" description="Запустите кампанию для генерации комментариев" />
      ) : (
        <div className="space-y-2">
          {comments.map((comment) => (
            <div key={comment.id} className="rounded-lg border border-gray-100 bg-gray-50/50 p-3">
              <div className="mb-2 flex items-start justify-between gap-2">
                {editingCommentId === comment.id ? (
                  <textarea
                    className="min-h-20 flex-1 rounded-md border border-gray-200 bg-white px-3 py-2 text-sm focus:border-navy-400 focus:outline-none focus:ring-2 focus:ring-navy-100"
                    value={editedText}
                    onChange={(event) => setEditedText(event.target.value)}
                  />
                ) : (
                  <p className="text-sm text-gray-800">{visibleGeneratedCommentText(comment)}</p>
                )}
                <ApprovalBadge status={comment.approval_status} />
              </div>
              {editingCommentId === comment.id && formError ? (
                <p className="mb-2 text-xs font-medium text-red-500">{formError}</p>
              ) : null}
              {mutationError ? <p className="mb-2 text-xs font-medium text-red-500">{mutationError}</p> : null}
              {comment.approval_status === 'pending' ? (
                <div className="flex flex-wrap gap-1.5">
                  {editingCommentId === comment.id ? (
                    <Button
                      size="sm"
                      variant="primary"
                      icon={<Save className="size-3" />}
                      onClick={() => {
                        setFormError(null)
                        let payload: NeuroGeneratedCommentUpdate
                        try {
                          payload = buildGeneratedCommentEditPayload(editedText)
                        } catch {
                          setFormError('Комментарий не может быть пустым')
                          return
                        }
                        mutations.edit.mutate(
                          { commentId: comment.id, payload },
                          {
                            onSuccess: () => {
                              setEditingCommentId(null)
                              setEditedText('')
                            },
                          },
                        )
                      }}
                      disabled={isMutating || !editedText.trim()}
                    >
                      Сохранить
                    </Button>
                  ) : (
                    <Button
                      size="sm"
                      variant="outline"
                      icon={<Pencil className="size-3" />}
                      onClick={() => {
                        setFormError(null)
                        setEditingCommentId(comment.id)
                        setEditedText(visibleGeneratedCommentText(comment))
                      }}
                      disabled={isMutating}
                    >
                      Редактировать
                    </Button>
                  )}
                  <Button
                    size="sm"
                    variant="primary"
                    icon={<Check className="size-3" />}
                    onClick={() => mutations.approve.mutate(comment.id)}
                    disabled={isMutating}
                  >
                    Одобрить
                  </Button>
                  <Button
                    size="sm"
                    variant="danger"
                    icon={<X className="size-3" />}
                    onClick={() =>
                      mutations.reject.mutate({
                        commentId: comment.id,
                        payload: { reason: rejectReason.trim() || 'rejected from UI' },
                      })
                    }
                    disabled={isMutating}
                  >
                    Отклонить
                  </Button>
                  <input
                    className="min-w-0 flex-1 rounded-md border border-gray-200 bg-white px-2 py-1 text-xs focus:border-navy-400 focus:outline-none focus:ring-2 focus:ring-navy-100"
                    placeholder="Причина отклонения"
                    value={rejectReason}
                    onChange={(event) => setRejectReason(event.target.value)}
                  />
                </div>
              ) : null}
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}
