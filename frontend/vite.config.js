import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// /api ile başlayan istekler geliştirme sırasında FastAPI'ye (8000) yönlendirilir
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
