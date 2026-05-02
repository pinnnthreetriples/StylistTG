import { execFileSync } from 'node:child_process'
import { mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const packageDir = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const repoRoot = resolve(packageDir, '../..')
const tempDir = mkdtempSync(resolve(tmpdir(), 'stylisttg-openapi-export-'))
const outIndex = process.argv.indexOf('--out')

if (outIndex === -1 || !process.argv[outIndex + 1]) {
  console.error('Usage: node ./scripts/export-openapi.mjs --out <path>')
  process.exit(2)
}

const outPath = resolve(packageDir, process.argv[outIndex + 1])

try {
  execFileSync('python', [resolve(repoRoot, 'backend/app/scripts/export_openapi.py'), '--out', outPath], {
    cwd: tempDir,
    env: {
      ...process.env,
      PYTHONPATH: resolve(repoRoot, 'backend'),
    },
    stdio: 'inherit',
  })
} finally {
  rmSync(tempDir, { force: true, recursive: true })
}
