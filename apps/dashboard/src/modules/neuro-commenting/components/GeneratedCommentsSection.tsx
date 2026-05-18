import { Button, Card, EmptyState, Skeleton } from '@stylisttg/ui'
import { Check, X } from 'lucide-react'

import { useGeneratedCommentMutations, useNeuroGeneratedComments } from '../hooks'

import { ApprovalBadge } from './ApprovalBadge'

export function GeneratedCommentsSection({ campaignId }: { campaignId: string | undefined }) {
  const commentsQuery = useNeuroGeneratedComments(campaignId)
  const mutations = useGeneratedCommentMutations(campaignId)
  const comments = commentsQuery.data?.items ?? []

  if (commentsQuery.isLoading) return <Skeleton className="h-40 w-full" />

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
                <p className="text-sm text-gray-800">{comment.final_text}</p>
                <ApprovalBadge status={comment.approval_status} />
              </div>
              {comment.approval_status === 'pending' ? (
                <div className="flex gap-1.5">
                  <Button
                    size="sm"
                    variant="primary"
                    icon={<Check className="size-3" />}
                    onClick={() => mutations.approve.mutate(comment.id)}
                    disabled={mutations.approve.isPending}
                  >
                    Одобрить
                  </Button>
                  <Button
                    size="sm"
                    variant="danger"
                    icon={<X className="size-3" />}
                    onClick={() => mutations.reject.mutate({ commentId: comment.id, payload: { reason: 'rejected from UI' } })}
                    disabled={mutations.reject.isPending}
                  >
                    Отклонить
                  </Button>
                </div>
              ) : null}
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}
