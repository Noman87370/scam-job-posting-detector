import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  base: './',
  build: {
    // Production build is served as static files by the FastAPI backend.
    outDir: '../backend/static',
    emptyOutDir: true,
  },
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
    },
  },
})
