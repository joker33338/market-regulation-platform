import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

// 后端解析服务默认端口 8180（scripts/start_parsing_app.ps1）
// 浏览器绝不直接携带 MinerU 官方 API Key，所有请求只打 FastAPI 后端
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  server: {
    host: '127.0.0.1',
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8180',
        changeOrigin: true
      }
    }
  }
})
