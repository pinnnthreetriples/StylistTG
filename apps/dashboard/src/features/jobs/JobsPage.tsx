import { PageHeader, SectionCard } from '@stylisttg/ui'

import { VirtualJobLogList } from '@/features/jobs/VirtualJobLogList'

export function JobsPage() {
  return (
    <div className="mx-auto grid max-w-6xl gap-5 px-5 py-6">
      <PageHeader
        eyebrow="Jobs"
        title="Worker Activity"
        description="Read-only foundation for queue visibility. This page does not enqueue or mutate jobs."
      />
      <SectionCard title="Virtualized job log">
        <VirtualJobLogList />
      </SectionCard>
    </div>
  )
}
