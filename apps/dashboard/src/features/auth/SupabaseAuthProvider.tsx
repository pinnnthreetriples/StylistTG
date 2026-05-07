import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import type { Session } from '@supabase/supabase-js'

import { SupabaseAuthContext, type AuthStatus, type SupabaseAuthContextValue } from '@/features/auth/SupabaseAuthContext'
import { resetApiAccessTokenProvider, setApiAccessTokenProvider } from '@/lib/apiClient'
import { getSupabaseAccessToken, getSupabaseClient, getSupabaseSession, isLocalE2EAuthBypassEnabled, isSupabaseConfigured } from '@/lib/supabase'

export function SupabaseAuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const sessionRef = useRef<Session | null>(null)
  const [session, setSession] = useState<Session | null>(null)
  const [status, setStatus] = useState<AuthStatus>(() => isLocalE2EAuthBypassEnabled() ? 'authenticated' : isSupabaseConfigured() ? 'loading' : 'unconfigured')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setApiAccessTokenProvider(() => sessionRef.current?.access_token ?? getSupabaseAccessToken())
    return () => resetApiAccessTokenProvider()
  }, [])

  useEffect(() => {
    if (isLocalE2EAuthBypassEnabled()) {
      void getSupabaseSession().then((nextSession) => {
        sessionRef.current = nextSession
        setSession(nextSession)
        setStatus('authenticated')
      })
      return
    }

    const supabase = getSupabaseClient()
    if (!isSupabaseConfigured() || !supabase) {
      return
    }

    let mounted = true
    supabase.auth.getSession().then(({ data }) => {
      if (!mounted) return
      sessionRef.current = data.session
      setSession(data.session)
      setStatus(data.session ? 'authenticated' : 'anonymous')
    })

    const { data } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      sessionRef.current = nextSession
      setSession(nextSession)
      setStatus(nextSession ? 'authenticated' : 'anonymous')
      if (!nextSession) queryClient.clear()
    })

    return () => {
      mounted = false
      data.subscription.unsubscribe()
    }
  }, [queryClient])

  const value = useMemo<SupabaseAuthContextValue>(() => ({
    session,
    status,
    error,
    signIn: async (email: string, password: string) => {
      const supabase = getSupabaseClient()
      if (!supabase) {
        setError('Supabase не настроен. Добавьте URL и publishable key.')
        return false
      }
      setError(null)
      const { error } = await supabase.auth.signInWithPassword({ email, password })
      if (error) {
        setError(authErrorMessage(error.message))
        return false
      }
      return true
    },
    signUp: async (email: string, password: string) => {
      const supabase = getSupabaseClient()
      if (!supabase) {
        setError('Supabase не настроен. Добавьте URL и publishable key.')
        return false
      }
      setError(null)
      const { error } = await supabase.auth.signUp({ email, password })
      if (error) {
        setError(authErrorMessage(error.message))
        return false
      }
      return true
    },
    signOut: async () => {
      const supabase = getSupabaseClient()
      if (!supabase) return
      await supabase.auth.signOut()
      sessionRef.current = null
      setSession(null)
      setStatus('anonymous')
      queryClient.clear()
    },
  }), [error, queryClient, session, status])

  return <SupabaseAuthContext.Provider value={value}>{children}</SupabaseAuthContext.Provider>
}

function authErrorMessage(message: string): string {
  const normalized = message.toLowerCase()
  if (normalized.includes('invalid login credentials')) {
    return 'Не удалось войти. Проверьте email и пароль.'
  }
  if (normalized.includes('email')) {
    return 'Проверьте email и попробуйте ещё раз.'
  }
  if (normalized.includes('password')) {
    return 'Пароль должен соответствовать требованиям Supabase.'
  }
  return 'Не удалось выполнить вход. Попробуйте ещё раз.'
}
