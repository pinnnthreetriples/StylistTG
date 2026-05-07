import { createContext, useContext } from 'react'
import type { Session } from '@supabase/supabase-js'

export type AuthStatus = 'loading' | 'authenticated' | 'anonymous' | 'unconfigured'

export type SupabaseAuthContextValue = {
  session: Session | null
  status: AuthStatus
  error: string | null
  signIn: (email: string, password: string) => Promise<boolean>
  signUp: (email: string, password: string) => Promise<boolean>
  signOut: () => Promise<void>
}

export const SupabaseAuthContext = createContext<SupabaseAuthContextValue | null>(null)

export function useSupabaseAuth(): SupabaseAuthContextValue {
  const context = useContext(SupabaseAuthContext)
  if (!context) {
    throw new Error('useSupabaseAuth must be used inside SupabaseAuthProvider')
  }
  return context
}
