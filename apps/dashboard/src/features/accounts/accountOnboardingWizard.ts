import { newIdempotencyKey } from '@stylisttg/api-client'

export type ParsedOnboardingPhone = {
  phone_number: string
  label: string | null
  position: number
  raw: string
}

const PHONE_PATTERN = /\+?\d[\d\s().-]{7,}\d/g

export function parseOnboardingPhones(rawInput: string, defaultLabel = ''): ParsedOnboardingPhone[] {
  const rows: ParsedOnboardingPhone[] = []
  const fallbackLabel = defaultLabel.trim() || null
  for (const line of rawInput.split(/\r?\n/)) {
    const matches = Array.from(line.matchAll(PHONE_PATTERN))
    for (const match of matches) {
      const normalized = normalizePhoneToken(match[0])
      if (!normalized) continue
      const hasMultiplePhones = matches.length > 1
      const trailing = line.slice((match.index ?? 0) + match[0].length).trim()
      const label = hasMultiplePhones || looksLikePhone(trailing) ? fallbackLabel : trailing.replace(/^[;\t,\s-]+/, '').trim() || fallbackLabel
      rows.push({
        phone_number: normalized,
        label,
        position: rows.length,
        raw: match[0],
      })
    }
  }
  return rows
}

export function makeOnboardingKey(prefix: string): string {
  return `${prefix}-${newIdempotencyKey()}`
}

function normalizePhoneToken(value: string): string | null {
  const digits = value.replace(/\D/g, '')
  if (digits.length < 10) return null
  return `+${digits}`
}

function looksLikePhone(value: string): boolean {
  return /\+?\d[\d\s().-]{7,}\d/.test(value)
}
