import { motion } from 'motion/react'
import type { ReactNode } from 'react'

import { staggerContainer, staggerItem } from '@/lib/motion'

export function AnimatedList({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <motion.div
      animate="visible"
      className={className}
      initial="hidden"
      variants={staggerContainer}
    >
      {children}
    </motion.div>
  )
}

export function AnimatedListItem({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <motion.div className={className} variants={staggerItem}>
      {children}
    </motion.div>
  )
}
