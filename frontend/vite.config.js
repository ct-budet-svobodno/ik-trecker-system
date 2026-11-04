import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// В docker-compose.dev.yml фронт ходит на /api, а Vite проксирует его на бэкенд.
const proxyTarget = process.env.VITE_PROXY_TARGET

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: proxyTarget ? { proxy: { '/api': proxyTarget } } : undefined,
})
