# UI/UX Quality Checklist

Use this checklist before major UI/refactor tasks to ensure SaaS-grade quality.

## Navigation
- [ ] All nav items have Russian labels
- [ ] Active state is visually distinct
- [ ] Mobile navigation works (hamburger menu)
- [ ] No dead links or disabled items without explanation
- [ ] Back/forward browser navigation works correctly

## Layout
- [ ] Pages use PageShell for consistent max-width
- [ ] Content doesn't overflow on mobile (320px min)
- [ ] Proper spacing between sections (gap-5)
- [ ] No horizontal scroll on any viewport

## Forms
- [ ] All inputs have labels (visible or aria-label)
- [ ] Error states are clearly visible
- [ ] Disabled states reduce opacity
- [ ] Loading states show spinner or disable interaction
- [ ] Russian placeholder and helper text

## Responsive
- [ ] Desktop sidebar visible on xl+
- [ ] Mobile menu works on smaller viewports
- [ ] Tables are scrollable or stack on mobile
- [ ] Touch targets meet 44×44px minimum

## Accessibility
- [ ] All interactive elements have focus styles
- [ ] ARIA roles on custom widgets (tabs, dialogs, menus)
- [ ] Color is not the only indicator of state
- [ ] Screen reader can navigate the page

## Animation
- [ ] Page transitions are 150-300ms
- [ ] Reduced motion preference is respected
- [ ] Errors and critical states are NOT animated
- [ ] Dense tables and logs are NOT animated

## Visual Hierarchy
- [ ] One clear h1 per page
- [ ] Eyebrow → title → description pattern for page headers
- [ ] Section cards have clear titles
- [ ] Actions are visually prominent (primary buttons)

## Empty States
- [ ] Every list/table has an empty state
- [ ] Empty state has Russian text
- [ ] Empty state suggests next action when applicable

## SaaS Dashboard Quality
- [ ] No raw technical English visible to user
- [ ] Status values are mapped through uiLabels
- [ ] Risk levels show Russian labels
- [ ] Loading states show skeletons or spinners
- [ ] Error states have recovery actions
