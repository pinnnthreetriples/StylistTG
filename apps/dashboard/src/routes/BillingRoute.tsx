import { Lock } from 'lucide-react'
import { Card, PageHeader, PageShell, ProductEmptyState } from '@stylisttg/ui'

import { AnimatedPage } from '@/components/ui/AnimatedPage'

export function BillingRoute() {
  return (
    <AnimatedPage>
      <PageShell className="grid gap-5">
        <PageHeader
          eyebrow="Биллинг"
          title="Биллинг и аналитика"
          description="Раздел подготовлен в архитектуре и будет добавлен позже."
        />
        <Card className="p-6">
          <ProductEmptyState
            title="Биллинг пока недоступен"
            description="Оплата, лимиты тарифа и расширенная аналитика появятся в отдельном безопасном PR. Сейчас этот раздел ничего не запускает и не меняет."
            action={<Lock className="size-5 text-gray-400" />}
          />
        </Card>
      </PageShell>
    </AnimatedPage>
  )
}
