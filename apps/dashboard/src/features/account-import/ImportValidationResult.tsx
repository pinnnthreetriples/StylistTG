import { SectionCard } from '@stylisttg/ui'

import type { AccountImportBatch } from '@/lib/api'

export function ImportValidationResult({ batch }: { batch: AccountImportBatch | null }) {
  const unsupported = (batch?.items ?? []).filter((item) => item.status === 'unsupported')

  return (
    <SectionCard title="Итог импорта">
      <div className="grid gap-3 text-sm md:grid-cols-3">
        <div>
          <p className="text-gray-500">Пачка</p>
          <p className="font-mono text-xs text-gray-900">{batch?.id ?? 'not created'}</p>
        </div>
        <div>
          <p className="text-gray-500">Неподдерживаемые строки</p>
          <p className="font-semibold text-gray-900">{unsupported.length}</p>
        </div>
        <div>
          <p className="text-gray-500">Политика</p>
          <p className="font-semibold text-gray-900">сначала предпросмотр, без автоматического входа</p>
        </div>
      </div>
      {unsupported.length > 0 ? (
        <div className="mt-3 rounded-lg border border-amber-100 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          Неподдерживаемые форматы сессий требуют ручного повторного входа; небезопасная конвертация не запускается.
        </div>
      ) : null}
    </SectionCard>
  )
}
