import { motion, AnimatePresence } from 'motion/react'
import type { ReactNode } from 'react'

import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@stylisttg/ui'

export function AnimatedDialog({
  open,
  onOpenChange,
  title,
  description,
  children,
  trigger,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  title?: ReactNode
  description?: ReactNode
  children: ReactNode
  trigger?: ReactNode
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      {trigger}
      <AnimatePresence>
        {open && (
          <DialogContent>
            <motion.div
              initial={{ opacity: 0, scale: 0.98 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.98 }}
              transition={{ duration: 0.2, ease: 'easeOut' }}
            >
              {(title || description) && (
                <DialogHeader>
                  {title && <DialogTitle>{title}</DialogTitle>}
                  {description && <DialogDescription>{description}</DialogDescription>}
                </DialogHeader>
              )}
              {children}
            </motion.div>
          </DialogContent>
        )}
      </AnimatePresence>
    </Dialog>
  )
}
