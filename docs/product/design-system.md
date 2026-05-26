# StylistTG Design System

## Visual Style

StylistTG is temporarily reset to a neutral shadcn baseline before a full redesign. The dashboard should stay usable, compact, and operational while avoiding project-specific visual identity.

## Token Baseline

Use shadcn/Tailwind semantic tokens only:

| Purpose | Token |
|---------|-------|
| Page/background | `background` |
| Main text | `foreground` |
| Panels/cards | `card`, `card-foreground` |
| Secondary surfaces | `muted`, `muted-foreground` |
| Primary actions | `primary`, `primary-foreground` |
| Errors/critical | `destructive` |
| Structure/focus | `border`, `input`, `ring` |

Do not add a custom palette until the new redesign direction is approved. Avoid brand color scales, decorative gradients, custom shadows, display fonts, and custom page-entry animations.

## Status Tones

Status tone names may remain in code as behavior labels for backwards compatibility, but their visual output should map to shadcn tokens:

- success/ready -> `muted` with `primary` emphasis
- warning/info/paused -> `muted` with `muted-foreground`
- danger/error/critical -> `destructive`
- neutral/unknown -> `muted` or `foreground`

## Typography

- Use system UI fonts only.
- Keep dashboard surfaces compact: `text-sm`, `text-xs`, and restrained headings.
- Do not use display fonts, hero-scale typography, negative tracking, or viewport-scaled type in product UI.
- Use system monospace for code/technical snippets.

## Spacing

Standard Tailwind spacing scale. Key patterns:

- Page padding: `px-4 py-6 sm:px-6`
- Section gaps: `gap-5`
- Card padding: `p-4`
- Element gaps: `gap-2` or `gap-3`

## Border Radius

- `--radius`: `0.625rem`
- Small buttons/badges: `rounded-md`
- Cards/sections: `rounded-lg` or `rounded-xl`
- Avatars/pills: `rounded-full`

## Motion

Use motion only where it clarifies state changes. Avoid decorative page-load sequences, custom stagger utilities, and custom keyframes during the redesign reset.

## Component Catalog

### Primitives
| Component | Usage |
|-----------|-------|
| `Button` | Primary actions, secondary, ghost, danger variants |
| `Input` | Text input fields with error state |
| `Textarea` | Multi-line text with error state |
| `Select` | Native select dropdown |
| `Checkbox` | Boolean with label |
| `Switch` | Toggle for settings |

### Data Display
| Component | Usage |
|-----------|-------|
| `Badge` | Inline status indicator |
| `StatusPill` | Status value with semantic dot |
| `StatusCard` | Labeled value card with tone |
| `MetricCard` | Numeric metric display |
| `DataTable` | Table wrapper |

### Layout
| Component | Usage |
|-----------|-------|
| `PageShell` | Standard page wrapper |
| `PageHeader` | Page title with eyebrow and actions |
| `SectionCard` | Titled card section |
| `Card` | Base card container |
| `SidebarNav` | Sidebar navigation |
| `TopBar` | Top header bar |
| `TableToolbar` | Table search/filter/actions bar |

### Forms
| Component | Usage |
|-----------|-------|
| `FormField` | Label + input + error/hint wrapper |
| `FieldError` | Inline error text |
| `FieldHint` | Inline hint text |
| `StickyActionBar` | Bottom bar for unsaved changes |

### Overlay & Interaction
| Component | Usage |
|-----------|-------|
| `Dialog` | Modal dialog |
| `DropdownMenu` | Contextual action menu |
| `Tooltip` | Hover information |
| `Tabs` | Tab navigation |
| `Alert` | Banner notification |
| `Skeleton` | Loading placeholder |

### Risk & Safety
| Component | Usage |
|-----------|-------|
| `RiskBadge` | Inline risk level indicator |
| `RiskSummaryCard` | Full risk overview card |
| `RiskReasonList` | List of risk reasons with severity |
| `RiskActionCard` | Actionable recommendation card |
| `CooldownPill` | Active safety pause indicator |
| `SafetyGatePanel` | Action-blocking panel |
| `AccountReadinessPanel` | Readiness checklist |

## Anti-patterns

1. Do not show raw API enums. Always map through `uiLabels.ts`.
2. Do not use English in UI. User-facing dashboard text must be Russian unless it is a protocol or product term.
3. Do not animate errors. Critical states should appear immediately.
4. Do not put Russian copy in generic primitives. Russian text belongs in app-level components.
5. Do not use `confirm()` dialogs. Use app-styled Dialog components.
6. Do not add ad-hoc colors or visual tokens before the redesign direction is approved.
7. Do not add components without TypeScript types.
