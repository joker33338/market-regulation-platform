import axios, { AxiosError } from 'axios'
import { ElMessage } from 'element-plus'

/**
 * 统一 Axios 实例
 * - 仅请求 FastAPI 后端 /api（开发期经 Vite 代理到 127.0.0.1:8180）
 * - 鉴权：Authorization: Bearer <token>（对齐 mineru_api.py 的 owner 依赖）
 * - Token 安全：内存优先 + sessionStorage 会话级；不写 localStorage、不打印到控制台或日志
 * - 生产环境应由服务端安全会话（HttpOnly Cookie / BFF）下发凭证，前端不长期持有 Token
 * - 浏览器绝不接触 MinerU 官方 API Key 与数据库口令
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

const client = axios.create({
  baseURL: '/',
  timeout: 30000
})

client.interceptors.request.use((config) => {
  const token = getToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

client.interceptors.response.use(
  (response) => response,
  (error: AxiosError<{ detail?: string }>) => {
    if (!error.response) {
      ElMessage.error('无法连接后端解析服务（127.0.0.1:8180），请确认服务已启动')
      return Promise.reject(error)
    }
    const status = error.response.status
    const raw = String(error.response.data?.detail || '')
    // 后端错误文案若意外包含凭证相关信息，一律降级为通用提示，不外泄
    const detail = /token|api[_-]?key|password|secret|bearer/i.test(raw) ? '' : raw
    if (status === 401 || status === 403) {
      ElMessage.error('API Token 无效或已过期，请在系统监控页重新配置')
    } else if (status === 413) {
      ElMessage.error(detail || '文件超过后端 100MB 上限，或单次任务文件数超过 20')
    } else if (status === 415) {
      ElMessage.error(detail || '文件类型或文件头校验未通过，请检查格式与内容')
    } else if (status === 503) {
      ElMessage.error(detail || '后端服务暂不可用，请确认解析服务已启动')
    } else {
      ElMessage.error(detail || `请求失败（HTTP ${status}）`)
    }
    return Promise.reject(error)
  }
)

export default client
