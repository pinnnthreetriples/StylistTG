import { execFileSync } from 'node:child_process'
import { mkdtempSync, readFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const packageDir = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const repoRoot = resolve(packageDir, '../..')
const tempDir = mkdtempSync(resolve(tmpdir(), 'stylisttg-openapi-'))
const tempOpenApi = resolve(tempDir, 'openapi.json')
const tempTypes = resolve(tempDir, 'schema.d.ts')
const committedOpenApi = resolve(packageDir, 'openapi.json')
const committedTypes = resolve(packageDir, 'src/generated/schema.d.ts')

try {
  execFileSync(process.execPath, [resolve(packageDir, 'scripts/export-openapi.mjs'), '--out', tempOpenApi], {
    cwd: packageDir,
    stdio: 'pipe',
  })
  const openapiTypescriptCli = resolve(repoRoot, 'node_modules/openapi-typescript/bin/cli.js')
  execFileSync(process.execPath, [openapiTypescriptCli, tempOpenApi, '-o', tempTypes], {
    cwd: packageDir,
    stdio: 'pipe',
  })

  const drift = [
    compareFile(committedOpenApi, tempOpenApi, 'packages/api-client/openapi.json'),
    compareFile(committedTypes, tempTypes, 'packages/api-client/src/generated/schema.d.ts'),
  ].filter(Boolean)

  if (drift.length > 0) {
    console.error('OpenAPI generated artifacts are stale:')
    for (const item of drift) console.error(`- ${item}`)
    console.error('')
    console.error('Run npm run generate:api and commit the changed OpenAPI artifacts.')
    process.exit(1)
  }

  console.log('OpenAPI generated artifacts are current.')
} finally {
  rmSync(tempDir, { force: true, recursive: true })
}

function compareFile(expectedPath, actualPath, label) {
  const expected = normalize(readFileSync(expectedPath, 'utf8'))
  const actual = normalize(readFileSync(actualPath, 'utf8'))
  if (expected === actual) return null
  return `${label} (${firstDifference(expected, actual)})`
}

function normalize(value) {
  return value.replace(/\r\n/g, '\n').trimEnd()
}

function firstDifference(expected, actual) {
  const expectedLines = expected.split('\n')
  const actualLines = actual.split('\n')
  const length = Math.max(expectedLines.length, actualLines.length)
  for (let index = 0; index < length; index += 1) {
    if (expectedLines[index] !== actualLines[index]) {
      return `first differing line ${index + 1}: committed=${summarizeLine(expectedLines[index])} generated=${summarizeLine(actualLines[index])}`
    }
  }
  return 'content differs'
}

function summarizeLine(line) {
  if (line === undefined) return '<missing>'
  return JSON.stringify(line.slice(0, 160))
}
