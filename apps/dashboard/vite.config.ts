import path from 'path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    watch: {
      ignored: ['**/backend/logs/**', '**/backend/storage/**', '**/backend/tdlib/**'],
    },
    proxy: {
      '/api': 'http://127.0.0.1:8002',
      '/health': 'http://127.0.0.1:8002',
      '/ready': 'http://127.0.0.1:8002',
      '/diagnostics': 'http://127.0.0.1:8002',
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  test: {
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json'],
      reportsDirectory: './coverage',
      include: ['src/**/*.{ts,tsx}'],
      exclude: [
        'src/**/*.test.{ts,tsx}',
        'src/assets/**',
        'src/main.tsx',
        'src/router.tsx',
      ],
      thresholds: {
        lines: 30,
        functions: 28,
        branches: 28,
        statements: 30,
      },
    },
  },
})
