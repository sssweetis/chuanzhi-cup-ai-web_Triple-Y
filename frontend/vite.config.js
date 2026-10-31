import { defineConfig } from 'vite'

export default defineConfig({
  server: { port: 5173, host: true, allowedHosts: true },
  build: { outDir: 'dist' }
})
