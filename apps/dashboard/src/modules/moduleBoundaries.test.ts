import { describe, expect, it } from 'vitest'

import authUiSecurityCompat from '../features/auth/authUiSecurity.ts?raw'
import useAuthBootstrapCompat from '../hooks/useAuthBootstrap.ts?raw'
import useAuthFlowCompat from '../hooks/useAuthFlow.ts?raw'
import useProfileDraftCompat from '../hooks/useProfileDraft.ts?raw'
import apiCompat from '../lib/api.ts?raw'
import authBatchesCompat from '../lib/authBatches.ts?raw'
import authCompat from '../lib/auth.ts?raw'
import dashboardCompat from '../lib/dashboard.ts?raw'
import boundaryPolicy from '../../../../docs/architecture/frontend-boundary-policy.json'

const BOUNDARY_POLICY = boundaryPolicy as {
  shared_module: string
  feature_modules: string[]
  allowed_shared_deep_imports: DeepImportPolicyEntry[]
  allowed_app_deep_module_imports: DeepImportPolicyEntry[]
}
type DeepImportPolicyEntry =
  | string
  | {
      key: string
    }
const SHARED_MODULE = BOUNDARY_POLICY.shared_module
const LEGACY_COMPAT_IMPORT_RE = /@\/(components\/auth|features\/auth|hooks\/use(AuthBootstrap|AuthFlow|ProfileDraft)|lib\/(auth|authBatches|dashboard))/
const moduleSources = import.meta.glob('./**/*.{ts,tsx}', {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>
const appSources = import.meta.glob('../**/*.{ts,tsx}', {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>
const MODULE_NAMES = Array.from(
  new Set(
    Object.keys(moduleSources)
      .map((path) => path.match(/^\.\/([^/]+)\//)?.[1])
      .filter((moduleName): moduleName is string => Boolean(moduleName)),
  ),
).sort()
const FEATURE_MODULES = MODULE_NAMES.filter((moduleName) => moduleName !== SHARED_MODULE)
const EXPECTED_FEATURE_MODULES = [...BOUNDARY_POLICY.feature_modules].sort()
const LEGACY_SHARED_DEEP_IMPORTS = new Set(
  BOUNDARY_POLICY.allowed_shared_deep_imports.map(policyEntryKey),
)
const LEGACY_COMPAT_DEEP_MODULE_IMPORTS = new Set(
  BOUNDARY_POLICY.allowed_app_deep_module_imports.map(policyEntryKey),
)
const IMPORT_SPECIFIER_RE =
  /(?:\bimport\s*\(\s*['"]([^'"]+)['"]\s*\)|\b(?:import|export)\s+(?:type\s+)?(?:[\s\S]*?\s+from\s+)?['"]([^'"]+)['"])/g

function readModule(moduleName: string): string {
  return Object.entries(moduleSources)
    .filter(([path]) => path.startsWith(`./${moduleName}/`))
    .map(([path, source]) => `// ${path}\n${source}`)
    .join('\n')
}

function moduleImportKey(path: string, importSpecifier: string): string | null {
  const aliasMatch = importSpecifier.match(/^@\/modules\/([^/]+)\/(.+)/)
  if (aliasMatch) {
    return `${path} -> @/modules/${aliasMatch[1]}/${aliasMatch[2]}`
  }

  if (!importSpecifier.startsWith('.')) {
    return null
  }

  const importerParts = path
    .replace(/^\.\//, '')
    .replace(/^\.\.\/modules\//, '')
    .split('/')
  importerParts.pop()
  const resolvedParts = [...importerParts]
  for (const part of importSpecifier.split('/')) {
    if (part === '.' || part === '') continue
    if (part === '..') {
      resolvedParts.pop()
      continue
    }
    resolvedParts.push(part)
  }

  const [targetModule, ...targetPath] = resolvedParts
  if (!MODULE_NAMES.includes(targetModule) || targetPath.length === 0) {
    return null
  }
  return `${path} -> @/modules/${targetModule}/${targetPath.join('/')}`
}

function policyEntryKey(entry: DeepImportPolicyEntry): string {
  return typeof entry === 'string' ? entry : entry.key
}

function deepModuleImportKeys(path: string, source: string): string[] {
  return Array.from(source.matchAll(IMPORT_SPECIFIER_RE))
    .map((match) => moduleImportKey(path, match[1] ?? match[2]))
    .filter((key): key is string => key !== null)
}

function moduleNameFromImportKey(key: string): string {
  const match = key.match(/ -> @\/modules\/([^/]+)\//)
  if (!match) throw new Error(`Invalid module import key: ${key}`)
  return match[1]
}

describe('frontend module boundaries', () => {
  it('requires public module indexes', () => {
    for (const moduleName of MODULE_NAMES) {
      expect(moduleSources[`./${moduleName}/index.ts`], moduleName).toBeDefined()
    }
  })

  it('discovers the active feature module set from source folders', () => {
    expect(MODULE_NAMES).toContain(SHARED_MODULE)
    expect(FEATURE_MODULES).toEqual(EXPECTED_FEATURE_MODULES)
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
        for (const importKey of deepModuleImportKeys(path, source)) {
          const targetModule = moduleNameFromImportKey(importKey)
          if (targetModule === moduleName || targetModule === SHARED_MODULE) continue
          if (FEATURE_MODULES.includes(targetModule)) {
            throw new Error(`${path} imports another feature module internals through ${importKey}`)
          }
        }
      }
    }
  })

  it('requires feature modules to use shared through the public shared index', () => {
    const observed = new Set<string>()
    for (const moduleName of FEATURE_MODULES) {
      for (const [path, source] of Object.entries(moduleSources)) {
        if (!path.startsWith(`./${moduleName}/`)) continue
        for (const importKey of deepModuleImportKeys(path, source)) {
          const targetModule = moduleNameFromImportKey(importKey)
          if (targetModule === SHARED_MODULE) {
            observed.add(importKey)
          }
        }
      }
    }

    expect(Array.from(observed).sort()).toEqual(Array.from(LEGACY_SHARED_DEEP_IMPORTS).sort())
  })

  it('blocks app-wide deep imports into module internals except compatibility wrappers', () => {
    const observed = new Set<string>()
    for (const [path, source] of Object.entries(appSources)) {
      if (path.startsWith('./')) continue
      for (const importKey of deepModuleImportKeys(path, source)) {
        observed.add(importKey)
      }
    }

    expect(Array.from(observed).sort()).toEqual(
      Array.from(LEGACY_COMPAT_DEEP_MODULE_IMPORTS).sort(),
    )
  })

  it('keeps shared module independent from feature modules', () => {
    for (const [path, source] of Object.entries(moduleSources)) {
      if (!path.startsWith(`./${SHARED_MODULE}/`)) continue
      for (const importKey of deepModuleImportKeys(path, source)) {
        const targetModule = moduleNameFromImportKey(importKey)
        if (FEATURE_MODULES.includes(targetModule)) {
          throw new Error(`${path} imports a feature module through ${importKey}`)
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
    expect(dashboardCompat).toContain("from '@/modules/account-editing'")
    expect(apiCompat).toContain("from '@/modules/account-editing'")

    expect(useAuthBootstrapCompat).toContain("from '@/modules/auth'")
    expect(useAuthFlowCompat).toContain("from '@/modules/auth'")
    expect(authUiSecurityCompat).toContain("from '@/modules/auth'")
    expect(authCompat).toContain("from '@/modules/auth/api'")
    expect(authBatchesCompat).toContain("from '@/modules/auth/batches'")
  })
})
