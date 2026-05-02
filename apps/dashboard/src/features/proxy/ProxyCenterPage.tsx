import { PageHeader, SectionCard } from '@stylisttg/ui'

export function ProxyCenterPage() {
  return (
    <div className="mx-auto grid max-w-6xl gap-5 px-5 py-6">
      <PageHeader
        eyebrow="Proxy Center"
        title="Proxy Inventory"
        description="Read-only SaaS area reserved for proxy health, assignments, and future routing controls."
      />
      <SectionCard title="Proxy operations">
        <p className="text-sm leading-6 text-gray-500">
          Existing per-account proxy diagnostics remain available in account settings. This foundation page does not
          create, test, or mutate proxies.
        </p>
      </SectionCard>
    </div>
  )
}
