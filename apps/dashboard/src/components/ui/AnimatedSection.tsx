import { motion } from 'motion/react'
import type { ReactNode } from 'react'

import { sectionEnter } from '@/lib/motion'

export function AnimatedSection({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <motion.div className={className} {...sectionEnter}>
      {children}
    </motion.div>
  )
}
