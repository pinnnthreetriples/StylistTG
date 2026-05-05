import { MotionConfig } from 'motion/react'
import type { ReactNode } from 'react'

/**
 * App-level motion configuration.
 * Wraps the app with MotionConfig to respect reduced motion preference.
 */
export function MotionProvider({ children }: { children: ReactNode }) {
  return (
    <MotionConfig reducedMotion="user">
      {children}
    </MotionConfig>
  )
}
