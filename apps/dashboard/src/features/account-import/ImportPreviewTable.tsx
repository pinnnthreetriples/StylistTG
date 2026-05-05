import { EmptyState, SectionCard, StatusPill } from '@stylisttg/ui'

import type { AccountImportBatch } from '@/lib/api'
import { labelImportStatus, labelRiskLevelShort } from '@/lib/uiLabels'

export function ImportPreviewTable({ batch }: { batch: AccountImportBatch | null }) {
  const items = batch?.items ?? []
  if (!batch) {
    return (
      <SectionCard title="Предпросмотр">
        <EmptyState title="Пакет не выбран" description="Создайте предпросмотр и проверьте пакет перед подтверждением." />
      </SectionCard>
    )
  }

  if (items.length === 0) {
    return (
      <SectionCard title="Предпросмотр">
        <EmptyState title="Пока нет строк предпросмотра" description="Запустите проверку, чтобы классифицировать данные аккаунтов." />
      </SectionCard>
    )
  }

  return (
    <SectionCard title="Предпросмотр" description="Показываются только скрытые подсказки и статус проверки. Материал сессий исключён.">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-left text-sm">
          <thead className="text-xs uppercase text-gray-500">
            <tr>
              <th className="py-2">Статус</th>
              <th className="py-2">Телефон</th>
              <th className="py-2">Юзернейм</th>
              <th className="py-2">Проверка</th>
              <th className="py-2">Риск</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {items.map((item) => (
              <tr key={item.id}>
                <td className="py-2">
                  <StatusPill tone={item.status === 'valid' ? 'green' : item.status === 'unsupported' ? 'amber' : 'muted'}>
                    {labelImportStatus(item.status)}
                  </StatusPill>
                </td>
                <td className="py-2 font-mono text-xs">{item.phone_hint ?? 'Скрыто'}</td>
                <td className="py-2">{item.username_hint ?? 'Не указан'}</td>
                <td className="py-2">{item.validation_message ?? labelImportStatus(item.validation_code ?? 'pending')}</td>
                <td className="py-2">{labelRiskLevelShort(item.risk_level)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </SectionCard>
  )
}
