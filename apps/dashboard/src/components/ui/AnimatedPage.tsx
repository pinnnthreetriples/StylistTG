import { motion } from 'motion/react'
import type { ReactNode } from 'react'

import { pageEnter } from '@/lib/motion'

export function AnimatedPage({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <motion.div className={className} {...pageEnter}>
      {children}
    </motion.div>
  )
}
