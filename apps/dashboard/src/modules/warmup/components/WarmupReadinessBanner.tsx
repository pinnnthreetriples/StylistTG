import { Alert, Badge } from '@stylisttg/ui'
import { Info, ShieldCheck } from 'lucide-react'

import type { WarmupReadiness } from '../types'

export function WarmupReadinessBanner({ readiness }: { readiness: WarmupReadiness | undefined }) {
  if (!readiness) return null

  const tone = readiness.workers_enabled && !readiness.dry_run ? 'green' : 'amber'
  return (
    <Alert icon={readiness.dry_run ? <Info className="size-4" /> : <ShieldCheck className="size-4" />}>
      <div className="flex flex-wrap items-center gap-2 text-navy-900">
        <Badge tone={tone}>{readiness.dry_run ? 'Безопасный режим' : 'Выполнение включено'}</Badge>
        <span className="text-sm font-semibold">
          {readiness.workers_enabled ? 'Воркеры подготовки активны' : 'Воркеры подготовки отключены'}
        </span>
      </div>
      <p className="mt-1 text-sm text-gray-600">
        Сейчас сессии только планируются, двигаются по дням и пишут журнал событий. Аккаунт не подписывается,
        не отправляет сообщения, не ставит реакции и не вызывает Telegram API.
      </p>
      <div className="mt-3 grid gap-2 text-xs text-gray-600 sm:grid-cols-3">
        <span className="rounded-md bg-white/70 px-2.5 py-1.5">1. Проверка готовности</span>
        <span className="rounded-md bg-white/70 px-2.5 py-1.5">2. План на 14 дней</span>
        <span className="rounded-md bg-white/70 px-2.5 py-1.5">3. Аудит без live-действий</span>
      </div>
    </Alert>
  )
}
