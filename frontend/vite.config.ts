import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  base: './',
  plugins: [react()],
  server: {
    port: 5174,
    proxy: {
      '/api': {
        target: `http://localhost:${process.env.OPENLAB_PORT || 8001}`,
        changeOrigin: true,
        ws: true,
      },
    },
  },
})
