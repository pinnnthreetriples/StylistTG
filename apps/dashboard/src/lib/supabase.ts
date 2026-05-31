import { createClient, type Session, type SupabaseClient } from '@supabase/supabase-js'

type SupabaseEnv = Record<string, string | undefined>

const env = import.meta.env as SupabaseEnv
const E2E_AUTH_BYPASS_KEY = 'stylisttg:e2e-auth-bypass'
// Synthetic tokens used only when the localhost E2E bypass is enabled —
// they never reach a real Supabase project.
const E2E_FIXTURE_PREFIX = 'e2e-fixture'
let client: SupabaseClient | null | undefined

export function isSupabaseConfigured(): boolean {
  return isLocalE2EAuthBypassEnabled() || Boolean(env.VITE_SUPABASE_URL && env.VITE_SUPABASE_PUBLISHABLE_KEY)
}

export function getSupabaseClient(): SupabaseClient | null {
  if (isLocalE2EAuthBypassEnabled()) return null
  if (!isSupabaseConfigured()) return null
  if (client === undefined) {
    client = createClient(env.VITE_SUPABASE_URL as string, env.VITE_SUPABASE_PUBLISHABLE_KEY as string)
  }
  return client
}

export async function getSupabaseSession(): Promise<Session | null> {
  if (isLocalE2EAuthBypassEnabled()) return buildE2ESession()
  const supabase = getSupabaseClient()
  if (!supabase) return null
  const { data } = await supabase.auth.getSession()
  return data.session
}

export async function getSupabaseAccessToken(): Promise<string | null> {
  return (await getSupabaseSession())?.access_token ?? null
}

export function isLocalE2EAuthBypassEnabled(): boolean {
  if (typeof window === 'undefined') return false
  const hostname = window.location.hostname
  const isLocalhost = hostname === '127.0.0.1' || hostname === 'localhost'
  return isLocalhost && window.localStorage.getItem(E2E_AUTH_BYPASS_KEY) === 'true'
}

function buildE2ESession(): Session {
  return {
    access_token: `${E2E_FIXTURE_PREFIX}-access`,
    refresh_token: `${E2E_FIXTURE_PREFIX}-refresh`,
    expires_in: 3600,
    expires_at: Math.floor(Date.now() / 1000) + 3600,
    token_type: 'bearer',
    user: {
      id: 'e2e-user',
      app_metadata: {},
      aud: 'authenticated',
      created_at: '2026-01-01T00:00:00.000Z',
      user_metadata: { email: 'qa@example.test' },
      email: 'qa@example.test',
    },
  } as Session
}
