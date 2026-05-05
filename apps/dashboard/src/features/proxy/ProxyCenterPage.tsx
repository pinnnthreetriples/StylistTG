import { PageHeader, SectionCard } from '@stylisttg/ui'

export function ProxyCenterPage() {
  return (
    <div className="mx-auto grid max-w-6xl gap-5 px-5 py-6">
      <PageHeader
        eyebrow="Прокси"
        title="Инвентарь прокси"
        description="Read-only раздел для глубоких ссылок. Основная работа с прокси находится внутри аккаунта."
      />
      <SectionCard title="Операции с прокси">
        <p className="text-sm leading-6 text-gray-500">
          Диагностика прокси по аккаунту доступна во вкладке аккаунта. Этот раздел не создаёт, не проверяет и не меняет прокси.
        </p>
      </SectionCard>
    </div>
  )
}
