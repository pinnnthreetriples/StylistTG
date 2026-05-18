import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: {
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json'],
      reportsDirectory: './coverage',
      include: ['src/**/*.ts'],
      exclude: ['src/**/*.test.ts', 'src/generated/**', 'src/index.ts'],
      thresholds: {
        lines: 39,
        functions: 27,
        branches: 62,
        statements: 38,
      },
    },
  },
})
