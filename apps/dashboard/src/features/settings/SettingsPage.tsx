import { PageHeader, SectionCard } from '@stylisttg/ui'

export function SettingsPage() {
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
    </div>
  )
}
