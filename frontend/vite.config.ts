import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

/**
 * v0.2.2：开发期同源代理到后端 8180。
 * - 页面只请求相对路径 `/api/...`，不硬编码 http://127.0.0.1:8180
 * - 代理目标可用 VITE_API_PROXY_TARGET 覆盖（例如候选镜像端口）；生产构建产物不含任何本地地址
 * - preview（构建产物预览）同样配置代理：否则 /api/* 会被本地预览服务以 404 拦截，
 *   使「预览服务未转发」被误判为「后端未加载契约」，联调结论失真
 * - 浏览器绝不直接携带 MinerU 官方 API Key，所有请求只打 FastAPI 后端
 */
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const proxyTarget = env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:8180'
  const apiProxy = {
    '/api': {
      target: proxyTarget,
      changeOrigin: true
    }
  }
  return {
    plugins: [vue()],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url))
      }
    },
    server: {
      host: '127.0.0.1',
      port: 5173,
      proxy: apiProxy
    },
    preview: {
      host: '127.0.0.1',
      port: 4173,
      proxy: apiProxy
    }
  }
})
