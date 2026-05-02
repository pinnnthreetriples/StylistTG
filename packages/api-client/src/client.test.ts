import { describe, expect, test } from 'vitest'

import { createStylistTgClient, resolveApiBaseUrl } from './index'
import type { paths } from './generated/schema'

describe('@stylisttg/api-client', () => {
  test('generated OpenAPI types can be imported', () => {
    const pathKeys: keyof paths | null = null

    expect(pathKeys).toBeNull()
  })

  test('creates a client with a normalized base URL', () => {
    const client = createStylistTgClient({ baseUrl: 'http://localhost:8000/' })

    expect(client).toBeTruthy()
    expect(resolveApiBaseUrl('http://localhost:8000/')).toBe('http://localhost:8000')
  })

  test('does not hardcode the staging URL', () => {
    expect(resolveApiBaseUrl(undefined)).toBe('')
    expect(String(createStylistTgClient)).not.toContain('code.run')
  })
})
