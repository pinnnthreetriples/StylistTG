import { describe, expect, it } from 'vitest'

import authUiSecurityCompat from '../features/auth/authUiSecurity.ts?raw'
import useAuthBootstrapCompat from '../hooks/useAuthBootstrap.ts?raw'
import useAuthFlowCompat from '../hooks/useAuthFlow.ts?raw'
import useProfileDraftCompat from '../hooks/useProfileDraft.ts?raw'
import apiCompat from '../lib/api.ts?raw'
import authBatchesCompat from '../lib/authBatches.ts?raw'
import authCompat from '../lib/auth.ts?raw'
import dashboardCompat from '../lib/dashboard.ts?raw'

const FEATURE_MODULES = ['account-editing', 'auth', 'warmup', 'neuro-commenting']
const PUBLIC_MODULE_IMPORT_RE = /@\/modules\/(account-editing|auth|warmup|neuro-commenting)(\/(?!$|index(?:\.ts)?['"])[^'"]+)/
const LEGACY_COMPAT_IMPORT_RE = /@\/(components\/auth|features\/auth|hooks\/use(AuthBootstrap|AuthFlow|ProfileDraft)|lib\/(auth|authBatches|dashboard))/
const moduleSources = import.meta.glob('./**/*.{ts,tsx}', {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>

function readModule(moduleName: string): string {
  return Object.entries(moduleSources)
    .filter(([path]) => path.startsWith(`./${moduleName}/`))
    .map(([path, source]) => `// ${path}\n${source}`)
    .join('\n')
}

describe('frontend module boundaries', () => {
  it('requires public module indexes', () => {
    for (const moduleName of FEATURE_MODULES) {
      expect(moduleSources[`./${moduleName}/index.ts`], moduleName).toBeDefined()
    }
  })

  it('keeps account-editing independent from warmup internals', () => {
    const source = readModule('account-editing')
    expect(source).not.toMatch(/@\/modules\/warmup\//)
    expect(source).not.toMatch(/\.\.\/warmup/)
  })

  it('keeps warmup independent from account-editing internals', () => {
    const source = readModule('warmup')
    expect(source).not.toMatch(/@\/modules\/account-editing\//)
    expect(source).not.toMatch(/\.\.\/account-editing/)
  })

  it('allows feature modules to use auth only through the public auth index', () => {
    for (const moduleName of ['account-editing', 'warmup', 'neuro-commenting']) {
      expect(readModule(moduleName)).not.toMatch(/@\/modules\/auth\//)
    }
  })

  it('blocks deep cross-module component imports', () => {
    for (const moduleName of FEATURE_MODULES) {
      expect(readModule(moduleName)).not.toMatch(/@\/modules\/[^'"]+\/components\//)
    }
  })

  it('requires feature modules to use other feature modules through public indexes', () => {
    for (const moduleName of FEATURE_MODULES) {
      for (const [path, source] of Object.entries(moduleSources)) {
        if (!path.startsWith(`./${moduleName}/`)) continue
        const violation = source.match(PUBLIC_MODULE_IMPORT_RE)
        if (violation?.[1] && violation[1] !== moduleName) {
          throw new Error(`${path} imports another feature module internals through ${violation[0]}`)
        }
      }
    }
  })

  it('keeps modules independent from legacy compatibility wrappers', () => {
    for (const moduleName of FEATURE_MODULES) {
      expect(readModule(moduleName)).not.toMatch(LEGACY_COMPAT_IMPORT_RE)
    }
  })

  it('keeps old frontend import paths as compatibility re-exports', () => {
    expect(useProfileDraftCompat).toContain("from '@/modules/account-editing'")
    expect(dashboardCompat).toContain("from '@/modules/account-editing/mappers'")
    expect(dashboardCompat).toContain("from '@/modules/account-editing/types'")
    expect(apiCompat).toContain("from '@/modules/account-editing'")

    expect(useAuthBootstrapCompat).toContain("from '@/modules/auth'")
    expect(useAuthFlowCompat).toContain("from '@/modules/auth'")
    expect(authUiSecurityCompat).toContain("from '@/modules/auth'")
    expect(authCompat).toContain("from '@/modules/auth/api'")
    expect(authBatchesCompat).toContain("from '@/modules/auth/batches'")
  })
})
