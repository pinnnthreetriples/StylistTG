# UI Component Sourcing Policy

## Overview

StylistTG may use external UI component libraries (e.g., 21st.dev, shadcn/ui, Radix) as sources of ideas and components. This document defines rules for how external components are adopted.

## Rules

### 1. Adapt, don't copy blindly
External components must be adapted to fit `packages/ui` conventions:
- Use the `cn()` utility for class merging
- Follow existing prop patterns (typed, with `className` support)
- Match the design token system (colors, spacing, radius)

### 2. No unnecessary dependencies
Before adding a new npm dependency for a component:
- Check if it can be built with existing primitives
- Verify the dependency is actively maintained
- Check bundle size impact
- Prefer native implementations for simple components (tooltip, dropdown)

### 3. Accessibility first
Every adopted component must:
- Have proper ARIA attributes
- Support keyboard navigation where applicable
- Work with screen readers
- Have accessible labels

### 4. Mobile-ready
Components must work on mobile viewports (min-width 320px). Test:
- Touch targets are at least 44×44px
- No horizontal overflow
- Responsive layouts

### 5. Reduced motion support
Components with animations must:
- Respect `prefers-reduced-motion` media query
- Work correctly with `MotionConfig reducedMotion="user"`
- Not rely on animation for conveying information

### 6. Token compliance
All new components must use the established design tokens:
- Colors from the navy/tangerine/honey/semantic palette
- Standard spacing scale
- Border radius from `--radius-*` tokens
- Standard shadow tokens

### 7. Russian UI policy
- Generic primitives in `packages/ui` must NOT contain Russian text
- Russian labels are applied at the app level (`apps/dashboard`)
- All user-facing text in the app must be Russian
- Technical enum values must be mapped through `uiLabels.ts`
