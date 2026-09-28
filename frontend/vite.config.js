import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // FastAPI (uvicorn src.api.main:app) on :8000 serves /api.
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
})
