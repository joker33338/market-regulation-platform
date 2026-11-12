/**
 * v0.2.2 统一 API 错误模型
 * 事实来源：docs/integration/frontend-api-contract.md「认证与通用规范 / 错误」章节
 *
 * 后端错误结构：{ "error": { "code": "..." } }（旧解析接口部分返回 { "detail": ... }）
 * 状态码：401/403/404/409/413/415/416/422/429/500/502/503/504
 * 前端一律不把后端可能含凭证、DSN、路径的原文透出到页面或控制台。
 */
import axios from 'axios'

export type ApiErrorKind =
  | 'no-permission'
  | 'outdated'
  | 'unavailable'
  | 'invalid'
  | 'conflict'
  | 'limit'
  | 'not-found'
  | 'canceled'
  | 'error'

/** 新增接口标记：这些路径 404 说明活动实例未加载 v0.2.2 路由，而非业务对象不存在 */
const NEW_API_MARKERS = [
  '/api/documents',
  '/api/review',
  '/api/knowledge/',
  '/api/stats/',
  '/api/system/',
  '/api/openapi.json',
  '/preview',
  '/source'
]

const SENSITIVE = /token|api[_-]?key|password|secret|bearer|dsn|postgres|pg_|private[_-]?key/i

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly kind: ApiErrorKind
  readonly hint: string

  constructor(status: number, code: string, kind: ApiErrorKind, hint: string) {
    super(hint)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.kind = kind
    this.hint = hint
  }
}

/** 后端文案掩码：任何疑似凭证/连接串的内容一律不外泄 */
function safeDetail(value: unknown): string {
  if (typeof value !== 'string') return ''
  if (SENSITIVE.test(value)) return ''
  return value.slice(0, 160)
}

function extractCode(data: unknown): string {
  if (!data || typeof data !== 'object') return ''
  const d = data as Record<string, unknown>
  const err = d.error
  if (err && typeof err === 'object' && 'code' in err) {
    const c = (err as Record<string, unknown>).code
    return typeof c === 'string' && !SENSITIVE.test(c) ? c : ''
  }
  return ''
}

function hintOf(status: number, kind: ApiErrorKind, code: string): string {
  const suffix = code ? `（${code}）` : ''
  switch (kind) {
    case 'no-permission':
      return status === 401
        ? `API Token 无效或未认证${suffix}，请在系统监控页配置有效会话凭证`
        : `无权访问该资源${suffix}，后端按 owner 隔离，跨用户访问返回 404`
    case 'outdated':
      return `接口不存在（HTTP 404）${suffix}：活动 8180 实例可能仍是 v0.2.1 旧镜像，未加载 v0.2.2 契约路由`
    case 'unavailable':
      return status === 0
        ? '无法连接后端服务，请确认 8180 端口与 Vite 代理可用'
        : `后端服务暂不可用（HTTP ${status}）${suffix}，请稍后重试`
    case 'conflict':
      return `操作被后端门禁拒绝（HTTP 409）${suffix}：幂等冲突、文件完整性校验或预览门禁未通过`
    case 'limit':
      return status === 429
        ? `请求过于频繁或模型并发达到上限（HTTP 429）${suffix}，请稍后重试`
        : `请求超过后端限制（HTTP ${status}）${suffix}`
    case 'invalid':
      return `请求参数或文件格式不被接受（HTTP ${status}）${suffix}`
    case 'not-found':
      return `资源不存在或已被移除（HTTP 404）${suffix}`
    case 'canceled':
      return '请求已取消'
    default:
      return `请求失败（HTTP ${status}）${suffix}`
  }
}

export function isApiError(value: unknown): value is ApiError {
  return value instanceof ApiError
}

/** 把任意异常归一化为 ApiError；axios 取消信号单独处理，不产生噪声 */
export function toApiError(value: unknown): ApiError {
  if (isApiError(value)) return value
  if (axios.isCancel(value)) return new ApiError(0, '', 'canceled', hintOf(0, 'canceled', ''))
  if (value instanceof Error && !axios.isAxiosError(value)) {
    return new ApiError(0, '', 'error', value.message.slice(0, 160))
  }
  const err = value as {
    response?: { status?: number; data?: unknown; config?: { url?: string } }
    request?: { responseURL?: string }
    config?: { url?: string }
    code?: string
  }
  const status = err?.response?.status ?? 0
  const url = err?.response?.config?.url || err?.config?.url || ''
  const code = extractCode(err?.response?.data)
  const detail = safeDetail(
    err?.response?.data && typeof err.response.data === 'object'
      ? (err.response.data as Record<string, unknown>).detail
      : ''
  )

  let kind: ApiErrorKind = 'error'
  if (status === 401 || status === 403) kind = 'no-permission'
  else if (status === 404) kind = NEW_API_MARKERS.some((m) => url.includes(m)) ? 'outdated' : 'not-found'
  else if (status === 409) kind = 'conflict'
  else if (status === 413 || status === 429) kind = 'limit'
  else if (status === 415 || status === 416 || status === 422 || status === 400) kind = 'invalid'
  else if (status === 0 || status === 500 || status === 502 || status === 503 || status === 504) kind = 'unavailable'

  // axios 超时：无 response，按不可达处理
  if (status === 0 && err?.code === 'ECONNABORTED') kind = 'unavailable'

  const hint = detail ? `${hintOf(status, kind, code)} · ${detail}` : hintOf(status, kind, code)
  return new ApiError(status, code, kind, hint)
}

/** 用户主动操作（上传、创建、重试）失败时显式提示；被动查询由 AsyncPanel 状态条呈现，避免刷屏 */
export function notifyApiError(value: unknown, fallback = '操作失败'): void {
  const e = toApiError(value)
  if (e.kind === 'canceled') return
  // 动态 import 避免模块循环；ElMessage 是全局单例
  import('element-plus').then(({ ElMessage }) => {
    ElMessage.error(e.hint || fallback)
  })
}

export function apiErrorHint(value: unknown): string {
  return toApiError(value).hint
}
