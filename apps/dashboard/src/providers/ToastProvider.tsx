/* eslint-disable react-refresh/only-export-components */
import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'

import { ToastViewport, type ToastItem } from '@/components/ui/toast'

type ToastContextValue = {
  notify: (toast: Omit<ToastItem, 'id'>) => void
  dismissToast: (id: string) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within ToastProvider')
  return ctx
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([])
  const toastTimeoutsRef = useRef<number[]>([])

  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const notify = useCallback((toast: Omit<ToastItem, 'id'>) => {
    const id = crypto.randomUUID()
    setToasts((prev) => [...prev.slice(-3), { ...toast, id }])
    const tid = window.setTimeout(
      () => setToasts((prev) => prev.filter((t) => t.id !== id)),
      toast.tone === 'error' ? 6000 : 3600,
    )
    toastTimeoutsRef.current.push(tid)
  }, [])

  useEffect(() => {
    return () => {
      toastTimeoutsRef.current.forEach((id) => window.clearTimeout(id))
      toastTimeoutsRef.current = []
    }
  }, [])

  return (
    <ToastContext.Provider value={{ notify, dismissToast }}>
      {children}
      <ToastViewport toasts={toasts} onDismiss={dismissToast} />
    </ToastContext.Provider>
  )
}
