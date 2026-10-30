import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // FastAPI server
      '/api': 'http://localhost:8000',
      // OpenTelemetry collector (OTLP/HTTP) from docker-compose
      '/v1/traces': 'http://localhost:4318',
    },
  },
})
