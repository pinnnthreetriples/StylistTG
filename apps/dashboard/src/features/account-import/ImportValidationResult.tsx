import { SectionCard } from '@stylisttg/ui'

import type { AccountImportBatch } from '@/lib/api'

export function ImportValidationResult({ batch }: { batch: AccountImportBatch | null }) {
  const unsupported = (batch?.items ?? []).filter((item) => item.status === 'unsupported')

  return (
    <SectionCard title="Итог импорта">
      <div className="grid gap-3 text-sm md:grid-cols-3">
        <div>
          <p className="text-muted-foreground">Пачка</p>
          <p className="font-mono text-xs text-foreground">{batch?.id ?? 'not created'}</p>
        </div>
        <div>
          <p className="text-muted-foreground">Неподдерживаемые строки</p>
          <p className="font-semibold text-foreground">{unsupported.length}</p>
        </div>
        <div>
          <p className="text-muted-foreground">Политика</p>
          <p className="font-semibold text-foreground">сначала предпросмотр, без автоматического входа</p>
        </div>
      </div>
      {unsupported.length > 0 ? (
        <div className="mt-3 rounded-lg border border-border bg-muted px-3 py-2 text-sm text-muted-foreground">
          Неподдерживаемые форматы сессий требуют ручного повторного входа; небезопасная конвертация не запускается.
        </div>
      ) : null}
    </SectionCard>
  )
}
