import { readFileSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'

const target = resolve(process.argv[2] ?? './src/generated/schema.d.ts')
const marker = '// fallow-ignore-file code-duplication\n'
const content = readFileSync(target, 'utf8')

if (!content.startsWith(marker)) {
  writeFileSync(target, `${marker}${content}`)
}
