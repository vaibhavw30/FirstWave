import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    fs: {
      allow: [
        path.resolve(__dirname, '..'),
      ],
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: './src/test/setup.jsx',
    globals: true,
    css: false,
  },
})
