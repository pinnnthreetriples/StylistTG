import { Card, EmptyState, Skeleton } from '@stylisttg/ui'

import { useNeuroAttempts } from '../hooks'
import type { NeuroAttempt } from '../types'

type AttemptsSectionProps =
  | { campaignId: string | undefined; attempts?: never; loading?: never; error?: never }
  | {
      campaignId?: never
      attempts: NeuroAttempt[]
      loading?: boolean
      error?: string | null
    }

export function AttemptsSection(props: AttemptsSectionProps) {
  if ('attempts' in props) {
    return (
      <AttemptsTable
        attempts={props.attempts ?? []}
        loading={props.loading ?? false}
        error={props.error ?? null}
      />
    )
  }
  return <CampaignAttemptsSection campaignId={props.campaignId} />
}

function CampaignAttemptsSection({ campaignId }: { campaignId: string | undefined }) {
  const attemptsQuery = useNeuroAttempts(campaignId)
  const attempts = attemptsQuery.data?.items ?? []

  return (
    <AttemptsTable
      attempts={attempts}
      loading={attemptsQuery.isLoading}
      error={attemptsQuery.isError ? 'Не удалось загрузить попытки' : null}
      total={attemptsQuery.data?.total ?? 0}
    />
  )
}

function AttemptsTable({
  attempts,
  loading,
  error,
  total = attempts.length,
}: {
  attempts: NeuroAttempt[]
  loading: boolean
  error: string | null
  total?: number
}) {
  if (error) return <Card className="p-4 text-sm text-red-600">{error}</Card>
  if (loading) return <Skeleton className="h-32 w-full" />

  return (
    <Card className="p-4">
      <h3 className="mb-3 text-sm font-semibold text-gray-900">Attempts ({total})</h3>
      {attempts.length === 0 ? (
        <EmptyState title="Нет попыток" description="Ручные отправки появятся здесь" />
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-xs">
            <thead className="text-gray-500">
              <tr>
                <th className="py-2 pr-3 font-medium">attempt id</th>
                <th className="py-2 pr-3 font-medium">status</th>
                <th className="py-2 pr-3 font-medium">comment id</th>
                <th className="py-2 pr-3 font-medium">account id</th>
                <th className="py-2 pr-3 font-medium">target id</th>
                <th className="py-2 pr-3 font-medium">telegram_message_id</th>
                <th className="py-2 pr-3 font-medium">error_code</th>
                <th className="py-2 pr-3 font-medium">created_at</th>
                <th className="py-2 pr-3 font-medium">sent_at</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 text-gray-700">
              {attempts.map((attempt) => (
                <tr key={attempt.id}>
                  <td className="py-2 pr-3">{attempt.id}</td>
                  <td className="py-2 pr-3 font-medium">{attempt.status}</td>
                  <td className="py-2 pr-3">{attempt.generated_comment_id}</td>
                  <td className="py-2 pr-3">{attempt.account_id ?? '-'}</td>
                  <td className="py-2 pr-3">{attempt.target_id ?? '-'}</td>
                  <td className="py-2 pr-3">{attempt.telegram_message_id ?? '-'}</td>
                  <td className="py-2 pr-3">{attempt.error_code ?? '-'}</td>
                  <td className="py-2 pr-3">{formatDateTime(attempt.created_at)}</td>
                  <td className="py-2 pr-3">{formatDateTime(attempt.sent_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}

function formatDateTime(value: string | null | undefined): string {
  return value ? new Date(value).toLocaleString('ru-RU') : '-'
}
