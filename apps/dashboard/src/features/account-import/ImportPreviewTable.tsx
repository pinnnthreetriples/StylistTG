import { EmptyState, SectionCard, StatusPill } from '@stylisttg/ui'

import type { AccountImportBatch } from '@/lib/api'

export function ImportPreviewTable({ batch }: { batch: AccountImportBatch | null }) {
  const items = batch?.items ?? []
  if (!batch) {
    return (
      <SectionCard title="Import preview">
        <EmptyState title="No import batch selected" description="Create a dry-run batch and validate it before confirmation." />
      </SectionCard>
    )
  }

  if (items.length === 0) {
    return (
      <SectionCard title="Import preview">
        <EmptyState title="No preview items yet" description="Run validation to classify uploaded/imported account data." />
      </SectionCard>
    )
  }

  return (
    <SectionCard title="Import preview" description="Only redacted hints and validation status are shown. Session material is excluded.">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-left text-sm">
          <thead className="text-xs uppercase text-gray-500">
            <tr>
              <th className="py-2">Status</th>
              <th className="py-2">Phone hint</th>
              <th className="py-2">Username</th>
              <th className="py-2">Validation</th>
              <th className="py-2">Risk</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {items.map((item) => (
              <tr key={item.id}>
                <td className="py-2">
                  <StatusPill tone={item.status === 'valid' ? 'green' : item.status === 'unsupported' ? 'amber' : 'muted'}>
                    {item.status}
                  </StatusPill>
                </td>
                <td className="py-2 font-mono text-xs">{item.phone_hint ?? 'redacted'}</td>
                <td className="py-2">{item.username_hint ?? 'unknown'}</td>
                <td className="py-2">{item.validation_code ?? item.validation_message ?? 'pending'}</td>
                <td className="py-2">{item.risk_level ?? 'unknown'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </SectionCard>
  )
}
