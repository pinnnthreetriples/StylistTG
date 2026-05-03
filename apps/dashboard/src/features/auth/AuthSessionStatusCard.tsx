import { SectionCard, StatusPill } from '@stylisttg/ui'

import type { TelegramAuthSession } from '@/lib/api'

export function AuthSessionStatusCard({ session }: { session: TelegramAuthSession | null }) {
  const status = session?.status ?? 'not_started'
  const tone = status === 'ready' ? 'green' : status === 'failed' ? 'red' : status.includes('waiting') ? 'amber' : 'muted'

  return (
    <SectionCard
      title="Live auth status"
      description="TDLib auth is explicit, audited, rate-limited, and disabled when live runtime is off."
    >
      <div className="flex flex-wrap items-center gap-2">
        <StatusPill tone={tone}>{status}</StatusPill>
        {session?.requires_code ? <StatusPill tone="amber">code required</StatusPill> : null}
        {session?.requires_password ? <StatusPill tone="amber">2FA required</StatusPill> : null}
        {session?.cooldown_until ? <StatusPill tone="red">cooldown active</StatusPill> : null}
      </div>
      <dl className="mt-4 grid gap-3 text-sm md:grid-cols-3">
        <div>
          <dt className="text-gray-500">Auth session</dt>
          <dd className="font-mono text-xs text-gray-900">{session?.id ?? 'not created'}</dd>
        </div>
        <div>
          <dt className="text-gray-500">Account link</dt>
          <dd className="font-mono text-xs text-gray-900">{session?.account_id ?? 'pending'}</dd>
        </div>
        <div>
          <dt className="text-gray-500">Last safe error</dt>
          <dd className="font-mono text-xs text-gray-900">{session?.last_error_code ?? 'none'}</dd>
        </div>
      </dl>
    </SectionCard>
  )
}
