import { Link } from '@tanstack/react-router'
import { Button, MetricCard, PageHeader, ProductEmptyState, SectionCard } from '@stylisttg/ui'

import { VirtualJobLogList } from '@/features/jobs/VirtualJobLogList'

export function JobsPage() {
  return (
    <div className="mx-auto grid max-w-6xl gap-5 px-5 py-6">
      <PageHeader
        eyebrow="Задачи"
        title="Задачи"
        description="Следите за активными задачами, ошибками и историей выполнения."
      />
      <div className="grid gap-3 md:grid-cols-4">
        <MetricCard label="Активные" value={0} />
        <MetricCard label="Ожидают действия" value={0} />
        <MetricCard label="Ошибки" value={0} />
        <MetricCard label="Завершённые" value={0} />
      </div>
      <ProductEmptyState
        title="Задач пока нет"
        description="Создайте задачу из карточки аккаунта после проверки риска."
        action={
          <Link to="/accounts">
            <Button type="button">Открыть аккаунты</Button>
          </Link>
        }
      />
      <SectionCard title="Расширенный журнал" description="Служебные события воркеров и история выполнения для диагностики.">
        <VirtualJobLogList />
      </SectionCard>
    </div>
  )
}
