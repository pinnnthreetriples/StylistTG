/**
 * Phase 1 · cross-module isolation guard banner.
 *
 * Показывается на любых страницах, где пользователь может попытаться выполнить
 * мутацию аккаунта, которым в данный момент управляет warmup-сессия с
 * execution_mode != dry_run. Backend-сторона enforce'ит этот контракт через
 * `ensure_not_isolated` в Campaigns/Broadcasts/Parsing — баннер только
 * предупреждает оператора заранее.
 */
import { Alert } from '@stylisttg/ui'
import { ShieldCheck } from 'lucide-react'

import { useWarmupIsolationStatus } from '../hooks'

export function WarmupIsolationBanner({
  accountId,
  className,
}: {
  accountId: string | null | undefined
  className?: string
}) {
  const isolationQuery = useWarmupIsolationStatus(accountId)
  const status = isolationQuery.data
  if (!status?.is_isolated || !status.claim) {
    return null
  }
  const acquired = formatAcquiredAt(status.claim.acquired_at)
  return (
    <Alert className={className} variant="info">
      <div className="flex items-start gap-2">
        <ShieldCheck className="mt-0.5 size-4 text-blue-600" aria-hidden />
        <div className="grid gap-1">
          <div className="text-sm font-semibold text-blue-900">
            Аккаунт сейчас занят прогревом
          </div>
          <p className="text-xs leading-5 text-blue-900/80">
            Пока активная сессия прогрева удерживает аккаунт, другие модули
            (Кампании, Рассылки, Парсинг) не смогут выполнять с ним действия.
            Это защита от конфликтов и неожиданных мутаций.
          </p>
          <div className="mt-1 grid gap-0.5 text-xs text-blue-900/70 sm:grid-cols-2">
            <span>
              <span className="font-semibold">Кем удерживается:</span>{' '}
              {status.claim.held_by}
            </span>
            <span>
              <span className="font-semibold">Причина:</span> {status.claim.reason}
            </span>
            {acquired ? (
              <span>
                <span className="font-semibold">С момента:</span> {acquired}
              </span>
            ) : null}
          </div>
        </div>
      </div>
    </Alert>
  )
}

function formatAcquiredAt(value: string): string | null {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return null
  return parsed.toLocaleString('ru-RU', {
    dateStyle: 'short',
    timeStyle: 'short',
  })
}
