import { motion } from 'motion/react'
import type { ReactNode } from 'react'

import { cardEnter } from '@/lib/motion'

export function AnimatedCard({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <motion.div className={className} {...cardEnter}>
      {children}
    </motion.div>
  )
}
