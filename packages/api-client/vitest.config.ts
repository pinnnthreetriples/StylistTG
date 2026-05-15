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
        lines: 35,
        functions: 25,
        branches: 60,
        statements: 35,
      },
    },
  },
})
