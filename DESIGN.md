# StylistTG Design Context

## Visual Register

StylistTG is product UI: quiet, utilitarian, and work-focused. First screen should be the usable dashboard or tool surface, not a landing page.

## Current State

The project is intentionally reset to a neutral shadcn baseline before a full redesign. Do not reintroduce a custom visual identity until the new design direction is provided.

## Temporary Baseline

- Use shadcn/Tailwind tokens: `background`, `foreground`, `card`, `muted`, `primary`, `border`, `input`, `ring`, and semantic states.
- Use system UI fonts only.
- Keep surfaces neutral, compact, and operational.
- Avoid project-specific palettes, decorative gradients, display fonts, custom shadows, custom page animations, and ornamental utilities.

## Layout

- Use constrained, information-dense layouts with predictable navigation.
- Prefer tables, lists, tabs, segmented controls, status rows, and compact panels for repeated workflows.
- Avoid nested cards. Use cards only for repeated items, modals, and truly framed tools.
- Keep fixed-format UI stable with explicit dimensions, grid tracks, and responsive constraints.

## Components

- Prefer shared `@stylisttg/ui` components when an equivalent exists.
- Buttons should use clear commands; icon buttons need accessible labels/tooltips.
- Use toggles/checkboxes for binary settings, segmented controls/tabs for modes, menus for option sets, and sliders/inputs for numeric values.
- Keep border radius restrained unless matching an existing component.

## Responsive Behavior

- Mobile and narrow desktop views should preserve task flow, not only stack cards.
- Text must not overflow buttons/cards or overlap adjacent content.
- Dense data should degrade to scrollable tables, compact rows, or prioritized fields.

## Impeccable Baseline

Run `npm run design:detect` before shipping meaningful dashboard UI changes. During this reset, remaining warnings should point to concrete leftover custom visuals or known shadcn-neutral choices.
