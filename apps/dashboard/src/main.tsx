import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider } from '@tanstack/react-router'
import './index.css'
import { MotionProvider } from '@/components/ui/MotionProvider'
import { SupabaseAuthProvider } from '@/features/auth/SupabaseAuthProvider'
import { queryClient } from '@/lib/queryClient'
import { router } from '@/router'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <SupabaseAuthProvider>
        <MotionProvider>
          <RouterProvider router={router} />
        </MotionProvider>
      </SupabaseAuthProvider>
    </QueryClientProvider>
  </StrictMode>,
)
