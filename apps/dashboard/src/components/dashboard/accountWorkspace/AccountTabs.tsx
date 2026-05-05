import { Tabs, TabsList, TabsTrigger } from '@stylisttg/ui'
import { useNavigate } from '@tanstack/react-router'

import { accountWorkspaceRoute, type AccountWorkspaceSection } from '@/lib/routes'

const tabs: { value: AccountWorkspaceSection; label: string }[] = [
  { value: 'profile', label: 'Профиль' },
  { value: 'stories', label: 'Истории' },
  { value: 'music', label: 'Музыка' },
  { value: 'proxy', label: 'Прокси' },
  { value: 'jobs', label: 'Задачи' },
  { value: 'risk', label: 'Риск и аудит' },
]

export function AccountTabs({
  accountId,
  activeSection,
}: {
  accountId: string
  activeSection: AccountWorkspaceSection
}) {
  const navigate = useNavigate()

  return (
    <div className="border-b border-gray-200/70 bg-white px-4 sm:px-6">
      <div className="mx-auto max-w-6xl">
        <Tabs
          value={activeSection}
          onValueChange={(section) => {
            void navigate({ href: accountWorkspaceRoute(accountId, section as AccountWorkspaceSection) })
          }}
        >
          <TabsList className="bg-transparent gap-0 rounded-none p-0">
            {tabs.map((tab) => (
              <TabsTrigger
                className="rounded-none border-b-2 border-transparent px-4 py-2.5 text-sm data-[state=active]:border-navy-400 data-[state=active]:bg-transparent"
                key={tab.value}
                value={tab.value}
              >
                {tab.label}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
      </div>
    </div>
  )
}
