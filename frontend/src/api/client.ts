import axios, { type AxiosError } from 'axios'
import { toApiError } from './errors'

/**
 * v0.2.2 统一请求层 —— 全站唯一 Axios 实例（不创建第二套）
 *
 * - Base URL 固定同源 `/`；开发期由 Vite 代理转发到后端 8180，生产构建不含任何本地地址
 * - 鉴权：Authorization: Bearer <会话凭证>，复用后端 Token→owner 映射
 * - Token 安全：内存优先 + sessionStorage 会话级；不写 localStorage、不打印到控制台/日志
 * - 浏览器绝不接触 MinerU 官方 API Key 与数据库凭据
 * - 错误统一归一化为 ApiError（见 errors.ts），被动查询由 AsyncPanel 呈现，主动操作显式提示
 * - 请求取消：各调用方传入 AbortSignal；幂等：创建任务带 Idempotency-Key
 */
const LEGACY_TOKEN_KEY = 'mrp_api_token'
const SESSION_TOKEN_KEY = 'mrp_session_token'

/** 仅内存持有；页面刷新后由 sessionStorage 恢复（关闭标签页即清除） */
let memoryToken = ''

function readSession(): string {
  try {
    return sessionStorage.getItem(SESSION_TOKEN_KEY) || ''
  } catch {
    return ''
  }
}

function writeSession(value: string) {
  try {
    if (value) sessionStorage.setItem(SESSION_TOKEN_KEY, value)
    else sessionStorage.removeItem(SESSION_TOKEN_KEY)
  } catch {
    /* 隐私模式禁用 storage 时仅保留内存态 */
  }
}

// 迁移：清除历史版本写入 localStorage 的长期 Token（不读取其内容、不输出）
try {
  localStorage.removeItem(LEGACY_TOKEN_KEY)
} catch {
  /* ignore */
}

export function getToken(): string {
  return memoryToken || readSession()
}

export function setToken(token: string) {
  memoryToken = token.trim()
  writeSession(memoryToken)
}

export function clearToken() {
  memoryToken = ''
  writeSession('')
}

export function hasToken(): boolean {
  return getToken().length > 0
}

/** 供系统监控页展示的存储方式说明（不含任何凭证内容） */
export const tokenStorageMode = '内存 + sessionStorage（会话级）· 仅开发期'

/** 请求超时：普通查询 30s；文件下载由调用方按需覆盖 */
export const DEFAULT_TIMEOUT_MS = 30_000

const client = axios.create({
  baseURL: '/',
  timeout: DEFAULT_TIMEOUT_MS
})

client.interceptors.request.use((config) => {
  const token = getToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

client.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => Promise.reject(toApiError(error))
)

export default client
