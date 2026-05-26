# StylistTG Product Context

## Register

product

## Product Purpose

StylistTG is an operator dashboard for Telegram account/profile automation, safety checks, warmup, auth batches, account editing, neuro-commenting, and runtime diagnostics.

The interface is not a marketing site. It should help an operator scan account state, understand risk, choose safe next actions, and recover from broken runtime conditions without guessing.

## Users

- Primary: internal operators managing many Telegram accounts and jobs.
- Secondary: engineers/support users debugging backend, Redis, worker, TDLib, proxy, and safety pipeline state.

## Tone

Calm, precise, operational, and trust-building. Prefer direct labels, explicit state, and clear affordances over playful copy.

## Product Principles

- Safety-first: risky or live actions must look gated, deliberate, and reversible where possible.
- Dense but readable: dashboards should optimize for scanning, comparison, and repeated use.
- State over decoration: visual weight should communicate status, risk, progress, ownership, and next action.
- No live behavior surprise: UI must not imply Telegram/TDLib actions happen unless gates and operator intent are clear.
- Russian UI copy is normal in dashboard surfaces; keep labels compact and concrete.

## Anti-References

- Marketing hero pages, oversized editorial sections, and decorative card-heavy layouts.
- One-note purple/blue AI gradients.
- Pure black overlays where a tinted dark neutral is enough.
- Gray text placed on colored status backgrounds.
- Nested cards that make operational data harder to scan.
