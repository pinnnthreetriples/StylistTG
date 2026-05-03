import { useQuery } from '@tanstack/react-query'
import { PageHeader, SectionCard, StatusPill } from '@stylisttg/ui'

import { auditEventsQueryOptions } from '@/lib/queries'

export function SettingsPage() {
  const auditEventsQuery = useQuery(auditEventsQueryOptions(12))

  return (
    <div className="mx-auto grid max-w-6xl gap-5 px-5 py-6">
      <PageHeader
        eyebrow="Settings"
        title="Workspace Settings"
        description="Foundation for workspace-level configuration. Existing execution policy controls remain on the current settings tab."
      />
      <SectionCard title="Deployment posture">
        <div className="grid gap-2 text-sm text-gray-600">
          <div>Adapter: PROFILE_EXECUTION_ADAPTER=mock</div>
          <div>TDLib live runtime: disabled until a separate image and volume PR.</div>
          <div>Cloud contour: staging resources only.</div>
        </div>
      </SectionCard>
      <SectionCard title="Audit History">
        <div className="mb-3 flex flex-wrap gap-2">
          <StatusPill tone="green">read-only</StatusPill>
          <StatusPill tone="amber">sanitized metadata</StatusPill>
          <StatusPill tone="muted">tenant scoped</StatusPill>
        </div>
        {auditEventsQuery.isPending ? (
          <div className="text-sm text-gray-500">Loading audit events...</div>
        ) : auditEventsQuery.isError ? (
          <div className="rounded-lg border border-amber-100 bg-amber-50 px-3 py-2 text-sm font-semibold text-amber-700">
            Audit history is unavailable.
          </div>
        ) : auditEventsQuery.data.items.length > 0 ? (
          <div className="grid gap-2">
            {auditEventsQuery.data.items.map((event) => (
              <div className="rounded-lg border border-gray-200/70 bg-gray-50 px-3 py-2" key={event.id}>
                <div className="text-sm font-semibold text-navy-900">{event.action}</div>
                <div className="mt-1 text-xs text-gray-500">
                  {event.entity_type}
                  {event.account_id ? ` · ${event.account_id}` : ''}
                  {' · '}
                  {new Date(event.created_at).toLocaleString()}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-sm text-gray-500">No sensitive audit events recorded yet.</div>
        )}
      </SectionCard>
    </div>
  )
}
