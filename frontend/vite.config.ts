import { defineConfig, loadEnv, type Plugin } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'
import type { IncomingMessage, ServerResponse } from 'node:http'

/**
 * 开发期同源代理：
 * - 页面只请求相对路径 `/api/...`，不硬编码后端地址；生产构建产物不含任何本地地址
 * - `VITE_API_PROXY_TARGET` 可指向 Agent C 提供的短生命周期隔离入口，
 *   用于 v0.2.3 draft-2 身份 / 审核写入联调
 * - server 与 preview 都配置代理，否则 /api/* 会被本地预览服务 404 拦截，
 *   使「预览服务未转发」被误判为「后端未加载契约」
 * - 浏览器绝不直接携带 MinerU 官方 API Key 或数据库凭据
 *
 * 写入保护（联调环境边界）：
 * 默认代理目标是正式 8180（v0.2.2），**不得默认向正式服务写入**。
 * 因此当目标仍是默认地址时，开发服务器在本地拦截 /api 下所有非只读请求并返回 403，
 * 不会把请求转发到正式 8180；GET / HEAD / OPTIONS 与契约中语义只读的 POST 预览/检索除外。
 * 隔离联调请显式设置 VITE_API_PROXY_TARGET 指向隔离入口（此时保护自动关闭）。
 * 仅在获准、且明知后果时才可用 VITE_ALLOW_WRITE_TO_DEFAULT_TARGET=1 解除保护。
 */
const DEFAULT_TARGET = 'http://127.0.0.1:8180'

/** 契约中语义只读的 POST：检索与结构预览，不产生业务写入 */
const READ_ONLY_POST_PATTERNS = [
  /^\/api\/knowledge\/search(?:\?|$)/,
  /^\/api\/review\/[^/]+\/preview(?:\?|$)/,
  /^\/api\/parse\/tasks\/[^/]+\/files\/[^/]+\/preview(?:\?|$)/
]

function isReadLikeRequest(req: IncomingMessage): boolean {
  const method = (req.method || 'GET').toUpperCase()
  if (method === 'GET' || method === 'HEAD' || method === 'OPTIONS') return true
  const url = req.url || ''
  return READ_ONLY_POST_PATTERNS.some((pattern) => pattern.test(url))
}

function apiWriteGuard(enabled: boolean): Plugin {
  const guard = (req: IncomingMessage, res: ServerResponse, next: () => void) => {
    const url = req.url || ''
    if (!url.startsWith('/api') || isReadLikeRequest(req)) return next()
    res.statusCode = 403
    res.setHeader('Content-Type', 'application/json; charset=utf-8')
    res.end(JSON.stringify({
      error: { code: 'frontend_write_guard' },
      detail: '默认代理目标为正式 8180，仅允许只读请求；隔离写入联调请设置 VITE_API_PROXY_TARGET 指向 Agent C 提供的短生命周期入口'
    }))
  }
  return {
    name: 'mrp-api-write-guard',
    configureServer(server) {
      if (enabled) server.middlewares.use(guard)
    },
    configurePreviewServer(server) {
      if (enabled) server.middlewares.use(guard)
    }
  }
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const proxyTarget = (env.VITE_API_PROXY_TARGET || DEFAULT_TARGET).replace(/\/+$/, '')
  const guardWrites =
    proxyTarget === DEFAULT_TARGET && env.VITE_ALLOW_WRITE_TO_DEFAULT_TARGET !== '1'
  const apiProxy = {
    '/api': {
      target: proxyTarget,
      changeOrigin: true
    }
  }
  return {
    plugins: [vue(), apiWriteGuard(guardWrites)],
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
