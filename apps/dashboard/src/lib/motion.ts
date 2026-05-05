/**
 * Motion animation presets for StylistTG.
 *
 * Usage:
 *   import { pageEnter, cardEnter } from '@/lib/motion'
 *   <motion.div {...pageEnter}>...</motion.div>
 *
 * All durations: 150–300ms. Easing: ease-out curves.
 * Animations are automatically disabled when the user prefers reduced motion
 * (handled by MotionConfig reducedMotion="user" at the app root).
 */
import type { Variants } from 'motion/react'

type CubicBezier = [number, number, number, number]

// --- Duration tokens ---
export const duration = {
  fast: 0.15,
  normal: 0.2,
  slow: 0.3,
} as const

// --- Easing tokens ---
export const easing = {
  default: [0.25, 0.1, 0.25, 1] as CubicBezier,
  enter: [0, 0, 0.2, 1] as CubicBezier,
  exit: [0.4, 0, 1, 1] as CubicBezier,
  spring: { type: 'spring' as const, stiffness: 400, damping: 30 },
}

// --- Preset props (spread onto motion elements) ---

export const pageEnter = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -8 },
  transition: { duration: duration.slow, ease: easing.enter },
} as const

export const sectionEnter = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: duration.normal, ease: easing.enter },
} as const

export const cardEnter = {
  initial: { opacity: 0, scale: 0.97 },
  animate: { opacity: 1, scale: 1 },
  transition: { duration: duration.normal, ease: easing.enter },
} as const

export const listItemEnter = {
  initial: { opacity: 0, x: -8 },
  animate: { opacity: 1, x: 0 },
  transition: { duration: duration.fast, ease: easing.enter },
} as const

export const subtleHover = {
  whileHover: { scale: 1.01 },
  transition: { duration: duration.fast },
} as const

export const tabTransition = {
  initial: { opacity: 0, y: 4 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -4 },
  transition: { duration: duration.fast, ease: easing.default },
} as const

export const modalTransition = {
  initial: { opacity: 0, scale: 0.96, y: 8 },
  animate: { opacity: 1, scale: 1, y: 0 },
  exit: { opacity: 0, scale: 0.96, y: 8 },
  transition: { duration: duration.normal, ease: easing.enter },
} as const

// --- Stagger variants (for AnimatedList) ---

export const staggerContainer: Variants = {
  hidden: {},
  visible: {
    transition: {
      staggerChildren: 0.04,
      delayChildren: 0.02,
    },
  },
}

export const staggerItem: Variants = {
  hidden: { opacity: 0, y: 6 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: duration.fast, ease: easing.enter },
  },
}
