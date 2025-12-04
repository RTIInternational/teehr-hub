import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0', // Allow external connections in Docker
    port: 5173,
    strictPort: true,
    allowedHosts: [
      ...(process.env.VITE_ALLOWED_HOSTS ? process.env.VITE_ALLOWED_HOSTS.split(',') : []),
      'localhost',
      '127.0.0.1'
    ],
    watch: {
      usePolling: true // Better for Docker file watching
    },
    proxy: {
      '/api': {
        target: process.env.VITE_API_BASE_URL || 'https://api.teehr.local.app.garden',
        changeOrigin: true,
        secure: false // Allow self-signed certificates
      }
    }
  },
  build: {
    outDir: 'build',
  },
  publicDir: 'public'
})