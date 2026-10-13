/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The dashboard talks to the backend directly (VITE_API_BASE); there is no proxy.
// Port 5173 is pinned (strictPort) because the backend's CORS list allows exactly it.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, strictPort: true, open: true },
  preview: { port: 5173, strictPort: true },
  test: { environment: 'node', include: ['src/**/*.test.ts'] },
})
