import { motion } from 'motion/react'
import { EmptyState, type EmptyStateProps } from '@stylisttg/ui'

import { sectionEnter } from '@/lib/motion'

export function AnimatedEmptyState(props: EmptyStateProps) {
  return (
    <motion.div {...sectionEnter}>
      <EmptyState {...props} />
    </motion.div>
  )
}
