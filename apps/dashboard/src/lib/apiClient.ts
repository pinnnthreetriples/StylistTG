import { createApiClient } from '@stylisttg/api-client'

import { getApiBaseUrl } from '@/lib/config'

type AccessTokenProvider = () => string | Promise<string | null> | null

let accessTokenProvider: AccessTokenProvider = () => null

export function setApiAccessTokenProvider(provider: AccessTokenProvider): void {
  accessTokenProvider = provider
}

export function resetApiAccessTokenProvider(): void {
  accessTokenProvider = () => null
}

export const dashboardApiClient = createApiClient({
  baseUrl: getTypedApiBaseUrl(),
  fetch: (...args) => globalThis.fetch(...args),
  getAccessToken: () => accessTokenProvider(),
})

function getTypedApiBaseUrl(): string {
  const configuredBaseUrl = getApiBaseUrl()
  if (configuredBaseUrl) return configuredBaseUrl
  if (typeof window !== 'undefined') return window.location.origin
  return 'http://localhost'
}
