import { motion } from 'motion/react'
import type { ReactNode } from 'react'

import { Tabs, TabsContent, TabsList, TabsTrigger } from '@stylisttg/ui'

export function AnimatedTabs({
  defaultValue,
  value,
  onValueChange,
  tabs,
}: {
  defaultValue?: string
  value?: string
  onValueChange?: (value: string) => void
  tabs: Array<{
    value: string
    label: ReactNode
    content: ReactNode
    disabled?: boolean
  }>
}) {
  const currentValue = value ?? defaultValue ?? tabs[0]?.value ?? ''
  const handleValueChange = onValueChange ?? (() => undefined)

  return (
    <Tabs value={currentValue} onValueChange={handleValueChange} className="w-full">
      <TabsList className="mb-4">
        {tabs.map((tab) => (
          <TabsTrigger key={tab.value} value={tab.value} disabled={tab.disabled}>
            {tab.label}
          </TabsTrigger>
        ))}
      </TabsList>

      {tabs.map((tab) => (
        <TabsContent key={tab.value} value={tab.value}>
          <motion.div
            initial={{ opacity: 0, y: 5 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -5 }}
            transition={{ duration: 0.2 }}
          >
            {tab.content}
          </motion.div>
        </TabsContent>
      ))}
    </Tabs>
  )
}
