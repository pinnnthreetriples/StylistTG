# StylistTG Design System

## Visual Style

StylistTG uses a warm, professional SaaS aesthetic with cream backgrounds, navy accents, and clear typographic hierarchy. The design is minimal and clean — no decorative gradients or heavy shadows.

## Color System

### Brand palette

| Token | Value | Usage |
|-------|-------|-------|
| `navy-50` – `navy-900` | Blue scale | Primary brand, active states, links |
| `tangerine-50` – `tangerine-700` | Orange scale | Warnings, attention, dirty indicators |
| `honey-50` – `honey-700` | Yellow/amber scale | Caution states, safety pauses |
| `cream` | `#F7F7F5` | Page background |

### Semantic colors

| Purpose | Token | Usage |
|---------|-------|-------|
| Primary | `navy-400` / `navy-500` | Buttons, links, active states |
| Success | `emerald-*` | Ready, OK, low risk |
| Warning | `amber-*` | Pauses, medium risk, needs attention |
| Danger | `red-*` | Errors, critical risk, failures |
| Info | `sky-*` | Informational badges, neutral status |
| Muted | `gray-*` | Secondary text, disabled states |

### Status tones (used by StatusPill, Badge, StatusCard)

- `green` → success / ready
- `amber` → warning / needs attention
- `red` → error / critical
- `blue` → informational
- `gray` → neutral / unknown / muted

## Typography

- **Heading**: Cabinet Grotesk (bold, 700-800)
- **Body**: General Sans → Geist Variable → system sans-serif
- **Display**: Cabinet Grotesk
- **Code/technical**: System monospace

### Scale

- Page title: `text-xl font-bold` or `text-lg font-bold`
- Section title: `text-sm font-semibold`
- Body: `text-sm`
- Small: `text-xs`
- Tiny: `text-[11px]`

## Spacing

Standard Tailwind spacing scale. Key patterns:

- Page padding: `px-4 py-6 sm:px-6`
- Section gaps: `gap-5`
- Card padding: `p-4`
- Element gaps: `gap-2` or `gap-3`

## Border Radius

- `--radius`: `0.625rem` (10px)
- Small buttons/badges: `rounded-md`
- Cards/sections: `rounded-lg` or `rounded-xl`
- Avatars/pills: `rounded-full`

## Shadows

- Soft: `shadow-soft` → `0 1px 3px rgba(0, 0, 0, 0.04)`
- Card: `shadow-sm`
- Modal: `shadow-xl`

## Motion

Duration tokens:
- Fast: 150ms (hover, micro-interactions)
- Normal: 200ms (sections, cards)
- Slow: 300ms (page transitions, modals)

Easing: `ease-out` / `cubic-bezier(0, 0, 0.2, 1)` for enters.

Rules:
- **DO**: Animate page enters, section appears, card reveals, list staggers
- **DON'T**: Animate errors, critical risk, dense tables, log entries, health failures
- Always respect `prefers-reduced-motion` (MotionConfig reducedMotion="user")

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
| `StatusPill` | Colored pill for status values |
| `StatusCard` | Labeled value card with tone |
| `MetricCard` | Large numeric metric display |
| `DataTable` | Table wrapper |

### Layout
| Component | Usage |
|-----------|-------|
| `PageShell` | Standard page wrapper (max-width, padding) |
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
| `Alert` | Banner notification (info/success/warning/error) |
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

1. **Don't show raw API enums** — Always map through `uiLabels.ts`
2. **Don't use English in UI** — All user-facing text must be Russian
3. **Don't animate errors** — Critical states should appear immediately
4. **Don't put Russian in generic primitives** — Russian text belongs in app-level components
5. **Don't use `confirm()` dialogs** — Use app-styled Dialog components
6. **Don't create ad-hoc status colors** — Use the tone system (green/amber/red/blue/gray)
7. **Don't add components without types** — Everything must be typed TypeScript
