import axios, { type AxiosError } from 'axios'
import { toApiError } from './errors'
import { emitAuthStateChange } from './authEvents'

/**
 * v0.2.2 统一请求层 —— 全站唯一 Axios 实例（不创建第二套）
 *
 * - Base URL 固定同源 `/`；开发期由 Vite 代理转发到后端（VITE_API_PROXY_TARGET 可指向隔离入口），
 *   生产构建不含任何本地地址；默认代理目标仅允许只读请求，见 vite.config.ts 的写入保护
 * - 鉴权：Authorization: Bearer <会话凭证>；v0.2.3 draft-2 由后端解析为不可变 Principal
 *   （principal_id / owner_id / roles / review_owner_scopes / credential_status），前端不推导身份
 * - Token 安全：内存优先 + sessionStorage 会话级；不写 localStorage、不打印到控制台/日志
 * - 浏览器绝不接触 MinerU 官方 API Key、正式 runtime 与数据库凭据
 * - 错误统一归一化为 ApiError（见 errors.ts），被动查询由 AsyncPanel 呈现，主动操作显式提示
 * - 401/403/404 广播认证状态，身份层据此清除旧身份与契约缓存，避免撤销后残留可写状态
 * - 请求取消：各调用方传入 AbortSignal；幂等：创建任务与审核写入带 Idempotency-Key
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
  (error: AxiosError) => {
    const apiError = toApiError(error)
    // 只广播状态码，不携带响应正文/凭证；身份层订阅后清除旧可写状态
    const currentToken = getToken()
    const sentAuthorization = String(error.config?.headers?.Authorization || '')
    const loginRequest = error.config?.url?.split('?')[0] === '/api/auth/login'
    // 密码错误属于登录表单；旧凭据的延迟响应也不能清掉刚建立的新会话。
    if (!loginRequest && currentToken && sentAuthorization === `Bearer ${currentToken}` &&
        (apiError.status === 401 || apiError.status === 403 || apiError.status === 404)) {
      emitAuthStateChange(apiError.status)
    }
    return Promise.reject(apiError)
  }
)

export default client
