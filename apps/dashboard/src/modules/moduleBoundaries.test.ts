import { describe, expect, it } from 'vitest'

const FEATURE_MODULES = ['account-editing', 'auth', 'warmup']
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
    for (const moduleName of ['account-editing', 'warmup']) {
      expect(readModule(moduleName)).not.toMatch(/@\/modules\/auth\//)
    }
  })

  it('blocks deep cross-module component imports', () => {
    for (const moduleName of FEATURE_MODULES) {
      expect(readModule(moduleName)).not.toMatch(/@\/modules\/[^'"]+\/components\//)
    }
  })
})
