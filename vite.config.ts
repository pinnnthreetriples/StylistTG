import path from 'path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

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
})
