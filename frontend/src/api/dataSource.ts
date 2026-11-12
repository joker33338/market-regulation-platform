import { computed, ref } from 'vue'
import { getRuntimeOpenApi } from './frontend'
import { hasToken } from './client'
import { toApiError } from './errors'
import type { DataSource } from './types'

/**
 * v0.2.2 接口能力状态 —— 全站唯一事实来源
 *
 * 重大变更（相对 v0.2.1）：能力开关**不再硬编码 true/false**。
 * 「源码已交付」与「运行期可用」是两件事：
 *   - 后端 feat/backend-api-v0.2.2 @ 4fc4cf1 已实现 22 条路径并导出离线 OpenAPI 快照；
 *   - 但活动 8180 实例仍为 v0.2.1 旧镜像，实测新接口全部 404。
 * 因此页面一律以运行期 GET /api/openapi.json 的探测结果为准：
 *   ready → 允许真实数据渲染；其余状态 → AsyncPanel 显示明确异常态 + 重试，绝不回退 DEMO。
 */

export type ContractState =
  | 'unknown'
  | 'ready'
  | 'no-permission'
  | 'outdated'
  | 'unavailable'
  | 'error'

export interface ContractMeta {
  probedAt: string
  version: string
  pathCount: number
  hint: string
}

export const contractState = ref<ContractState>('unknown')

export const contractMeta = ref<ContractMeta>({
  probedAt: '',
  version: '',
  pathCount: 0,
  hint: '尚未探测运行期接口'
})

export const contractLabel = computed<Record<ContractState, string>>(() => ({
  unknown: '未探测',
  ready: '契约就绪',
  'no-permission': '未认证 / 无权限',
  outdated: '服务未加载 v0.2.2 契约',
  unavailable: '服务不可达',
  error: '探测失败'
}))

/** v0.2.3 新增路由（离线契约 29 路径减去 v0.2.2 的 22 路径） */
export const V023_REVIEW_WRITE_ROUTES = [
  '/api/review/{parse_id}/approve',
  '/api/review/{parse_id}/reject',
  '/api/review/{parse_id}/mark-error',
  '/api/review/{parse_id}/save-revision'
] as const
export const V023_READ_ROUTES = [
  '/api/review/{parse_id}/events',
  '/api/system/resources',
  '/api/system/audit-logs'
] as const

/** 运行期 OpenAPI 实际返回的路径；源码里存在某接口不等于活动服务已加载 */
export const runtimePaths = ref<string[]>([])

/**
 * 运行期 OpenAPI 实际支持的「方法 + 路径」。
 * 路径存在不等于方法可用：例如 /api/documents/{file_id} 只有 GET，
 * 若仅按路径集合判断就会错误解锁删除按钮，因此方法级能力必须单独比对。
 */
export const runtimeMethodPaths = ref<string[]>([])
const HTTP_METHODS = new Set(['get', 'post', 'put', 'patch', 'delete', 'head', 'options', 'trace'])

export function collectRuntimeMethodPaths(doc: unknown): string[] {
  const result: string[] = []
  if (!doc || typeof doc !== 'object') return result
  const paths = (doc as { paths?: Record<string, unknown> }).paths
  if (!paths || typeof paths !== 'object') return result
  for (const [path, def] of Object.entries(paths)) {
    if (!def || typeof def !== 'object') continue
    for (const key of Object.keys(def as Record<string, unknown>)) {
      if (HTTP_METHODS.has(key.toLowerCase())) result.push(`${key.toUpperCase()} ${path}`)
    }
  }
  return result
}

/** 纯粹的路径集合比对，不依赖探测状态（供 probeContract 内部使用） */
function pathsInclude(required: readonly string[], paths: string[]): boolean {
  return required.every((path) => paths.includes(path))
}

/** 所有入参路径都必须在运行期 OpenAPI 中出现，才允许启用对应能力 */
export function hasRuntimeRoutes(required: readonly string[]): boolean {
  if (contractState.value !== 'ready' || runtimePaths.value.length === 0) return false
  return pathsInclude(required, runtimePaths.value)
}

/** 方法级门控：只有运行期契约确实声明了该 HTTP 方法，才允许启用对应写操作 */
export function hasRuntimeMethod(method: string, path: string): boolean {
  if (contractState.value !== 'ready' || runtimeMethodPaths.value.length === 0) return false
  return runtimeMethodPaths.value.includes(`${method.toUpperCase()} ${path}`)
}

export function hasV023ReviewWriteRoutes(): boolean {
  return hasRuntimeRoutes(V023_REVIEW_WRITE_ROUTES)
}
export function hasV023ReviewEvents(): boolean {
  return hasRuntimeRoutes(['/api/review/{parse_id}/events'])
}
export function hasV023Monitoring(): boolean {
  return hasRuntimeRoutes(['/api/system/resources', '/api/system/audit-logs'])
}
/** 文档筛选新参数没有独立路径，用同批新增的监控路由作为 v0.2.3 运行期标记 */
export function hasV023DocumentFilters(): boolean {
  return hasRuntimeRoutes(['/api/system/resources'])
}

let inflight: Promise<ContractState> | null = null

/** 运行期能力探测；并发调用共用同一 Promise，避免页面切换重复请求 */
export function probeContract(force = false): Promise<ContractState> {
  if (!force && inflight) return inflight
  inflight = (async () => {
    if (!hasToken()) {
      contractState.value = 'no-permission'
      contractMeta.value = {
        probedAt: new Date().toISOString(), version: '', pathCount: 0,
        hint: '未配置 API Token，所有 /api/* 请求会被后端拒绝（401）。请在系统监控页配置会话凭证。'
      }
      return contractState.value
    }
    try {
      const doc = await getRuntimeOpenApi()
      const paths = doc && typeof doc === 'object' && doc.paths ? Object.keys(doc.paths) : []
      const hasNewRoutes = paths.includes('/api/documents') && paths.includes('/api/system/health')
      runtimePaths.value = paths
      runtimeMethodPaths.value = collectRuntimeMethodPaths(doc)
      const hasV023 = pathsInclude(V023_REVIEW_WRITE_ROUTES, paths)
      contractMeta.value = {
        probedAt: new Date().toISOString(),
        version: doc?.info?.version || '',
        pathCount: paths.length,
        hint: hasNewRoutes
          ? `运行期 OpenAPI 返回 ${paths.length} 条路径（${doc?.info?.version || '版本未知'}）；${hasV023 ? 'v0.2.3 审核台账等新增路由已加载，写按钮仍须逐对象确认写授权' : '未加载 v0.2.3 新增路由，审核写入等能力保持禁用'}`
          : `运行期 OpenAPI 仅返回 ${paths.length} 条路径，缺少 /api/documents 等新增路由；活动实例仍是旧镜像`
      }
      contractState.value = hasNewRoutes ? 'ready' : 'outdated'
    } catch (err) {
      const e = toApiError(err)
      contractState.value =
        e.kind === 'no-permission' ? 'no-permission'
          : e.kind === 'outdated' || e.kind === 'not-found' ? 'outdated'
            : e.kind === 'unavailable' ? 'unavailable' : 'error'
      contractMeta.value = {
        probedAt: new Date().toISOString(), version: '', pathCount: 0, hint: e.hint
      }
    }
    return contractState.value
  })().finally(() => {
    inflight = null
  })
  return inflight
}

export function isContractReady(): boolean {
  return contractState.value === 'ready'
}

export function resetContractState() {
  contractState.value = 'unknown'
  runtimePaths.value = []
  runtimeMethodPaths.value = []
  contractMeta.value = { probedAt: '', version: '', pathCount: 0, hint: '已重置，等待重新探测' }
}

/** 写操作 / 未实现能力的统一禁用说明 */
export function unimplementedHint(api: string): string {
  return `后端契约明确不支持该操作（需 ${api}），前端保持禁用，不做本地假成功`
}

/* ───────────── 源码契约清单（来自离线 OpenAPI 快照，非运行期探测结果） ───────────── */

export interface ContractRoute {
  method: string
  path: string
  page: string
  group: 'legacy' | 'new'
}

export const CONTRACT_ROUTES: ContractRoute[] = [
  { method: 'GET', path: '/api/parse/info', page: '解析中心 / 系统监控', group: 'legacy' },
  { method: 'POST', path: '/api/parse/files', page: '文档管理（上传）', group: 'legacy' },
  { method: 'POST', path: '/api/parse/tasks', page: '解析中心（创建任务）', group: 'legacy' },
  { method: 'GET', path: '/api/parse/tasks/{task_id}', page: '解析中心 / 文档管理', group: 'legacy' },
  { method: 'GET', path: '/api/parse/tasks/{task_id}/errors', page: '解析中心', group: 'legacy' },
  { method: 'POST', path: '/api/parse/tasks/{task_id}/resume', page: '解析中心', group: 'legacy' },
  { method: 'POST', path: '/api/parse/tasks/{task_id}/cancel', page: '解析中心', group: 'legacy' },
  { method: 'GET', path: '/api/parse/tasks/{task_id}/results', page: '解析中心 / 文档管理', group: 'legacy' },
  { method: 'GET', path: '/api/parse/tasks/{task_id}/files/{file_id}/artifact', page: '解析中心', group: 'legacy' },
  { method: 'GET', path: '/api/documents', page: '文档管理（列表/搜索/分页）', group: 'new' },
  { method: 'GET', path: '/api/documents/{file_id}', page: '文档管理（详情）', group: 'new' },
  { method: 'GET', path: '/api/documents/{file_id}/parse-history', page: '文档管理（解析历史）', group: 'new' },
  { method: 'GET', path: '/api/parse/tasks', page: '解析中心（任务列表）', group: 'new' },
  { method: 'GET/HEAD', path: '/api/parse/files/{file_id}/source', page: '文档管理 / 审核中心（原件）', group: 'new' },
  { method: 'GET', path: '/api/review', page: '审核中心（完整待复核队列）', group: 'new' },
  { method: 'GET', path: '/api/review/{parse_id}', page: '审核中心（详情/候选对照）', group: 'new' },
  { method: 'POST', path: '/api/review/{parse_id}/preview', page: '入库管理（已持久化结果预览）', group: 'new' },
  { method: 'POST', path: '/api/parse/tasks/{task_id}/files/{file_id}/preview', page: '入库管理（Chunk 预览）', group: 'new' },
  { method: 'GET', path: '/api/knowledge/versions', page: '入库管理（版本列表）', group: 'new' },
  { method: 'GET', path: '/api/knowledge/versions/{version}', page: '入库管理（版本详情）', group: 'new' },
  { method: 'POST', path: '/api/knowledge/search', page: '法规检索', group: 'new' },
  { method: 'GET', path: '/api/stats/overview', page: '首页工作台', group: 'new' },
  { method: 'GET', path: '/api/system/health', page: '首页 / 系统监控', group: 'new' },
  { method: 'GET', path: '/api/openapi.json', page: '运行期能力探测', group: 'new' }
]

export interface MissingCapability {
  priority: 'P0' | 'P1'
  api: string
  usage: string
  impact: string
}

/** 后端契约「明确不支持」清单 —— 前端一律禁用或空态，不自行写库 */
/* ───────────── 历史兼容层 ─────────────
 * src/api/mock/** 共 9 个模块是 v0.2.1 遗留的演示数据层，v0.2.2 起**页面零引用**（已隔离）。
 * 下列导出仅为让这些隔离模块仍可编译而保留，禁止任何新页面调用：
 * 页面真实数据一律来自 frontend.ts / parse.ts，能力判定一律来自 contractState。
 * ------------------------------------------------------------------ */

/** @deprecated 禁止在页面使用 DEMO 结果 */
export const DEMO_NOTE = '历史演示数据层（已隔离，页面禁止引用）'

export interface DataResult<T> {
  data: T
  source: DataSource
  note?: string
}

/** @deprecated 禁止在页面使用 DEMO 结果 */
export function demoResult<T>(data: T, note: string = DEMO_NOTE): DataResult<T> {
  return { data, source: 'demo', note }
}

/** @deprecated 禁止用于能力判定 */
export function realResult<T>(data: T): DataResult<T> {
  return { data, source: 'real' }
}

/**
 * @deprecated v0.2.2 已废弃静态能力开关。
 * 全部为 false：运行期是否可用必须由 GET /api/openapi.json 探测（contractState）决定，
 * 任何 true 都可能把「源码已交付」误当成「活动服务已加载」。
 */
export const apiCapabilities = {
  knowledgeSearch: false,
  dashboardStats: false,
  documentList: false,
  reviewRead: false,
  reviewWrite: false,
  parseTaskList: false,
  sourceFile: false,
  ingestion: false,
  systemHealth: false
} as const

export type CapabilityKey = keyof typeof apiCapabilities

/** @deprecated 使用 isContractReady() */
export function isDemo(_key: CapabilityKey): boolean {
  return !isContractReady()
}

export const MISSING_CAPABILITIES: MissingCapability[] = [
  { priority: 'P0', api: 'POST /api/review/{parse_id}/approve', usage: '审核通过', impact: 'v0.2.3 源码契约已交付；运行期未加载路由或当前 owner 未获写授权时保持禁用，绝不本地假成功' },
  { priority: 'P0', api: 'POST /api/review/{parse_id}/reject', usage: '退回重新解析', impact: '同上：双门控（运行期路径 + 详情 review_write_supported / review_ledger.available）' },
  { priority: 'P0', api: 'POST /api/review/{parse_id}/mark-error', usage: '标记识别错误', impact: '同上：必填 reason 与真实 page，失败按 409/422/403/503 明确提示' },
  { priority: 'P0', api: 'POST /api/review/{parse_id}/save-revision', usage: '保存人工修订（含审计留痕）', impact: '同上：修订正文按不可信纯文本渲染，不覆盖原始解析结果' },
  { priority: 'P1', api: 'POST /api/ingestion/batches', usage: '正式入库批次 / 批次授权', impact: '入库页「发起入库批次」禁用' },
  { priority: 'P1', api: 'POST /api/ingestion/publish、/rollback', usage: 'ACTIVE 发布与回滚', impact: '入库页不开放发布/回滚' },
  { priority: 'P1', api: 'GET /api/parse/tasks/{task_id}/logs', usage: '结构化解析阶段日志', impact: '解析中心日志仅能展示 public(task) 真实字段' },
  { priority: 'P1', api: 'GET /api/system/api-logs、/error-logs', usage: 'API 访问日志 / 错误日志', impact: '仍无真实持久化事件来源，系统监控保持「未接入」空态，不编造历史事件' },
  { priority: 'P1', api: 'DELETE /api/documents/{file_id}', usage: '文档删除（单行 / 多选批量）', impact: 'v0.2.2 与 v0.2.3 契约均只声明 GET，原始证据只读；前端多选可用，删除按钮按运行期方法级门控保持禁用，不做本地假删除' }
]

/** v0.2.3 相对 v0.2.2 新增的 7 条路径（源码契约清单，运行期是否可用看 hasRuntimeRoutes） */
export const CONTRACT_ROUTES_V023: ContractRoute[] = [
  { method: 'POST', path: '/api/review/{parse_id}/approve', page: '审核中心（审核通过）', group: 'new' },
  { method: 'POST', path: '/api/review/{parse_id}/reject', page: '审核中心（退回）', group: 'new' },
  { method: 'POST', path: '/api/review/{parse_id}/mark-error', page: '审核中心（标记错误）', group: 'new' },
  { method: 'POST', path: '/api/review/{parse_id}/save-revision', page: '审核中心（保存修订）', group: 'new' },
  { method: 'GET', path: '/api/review/{parse_id}/events', page: '审核中心（台账事件）', group: 'new' },
  { method: 'GET', path: '/api/system/resources', page: '系统监控（API 进程资源）', group: 'new' },
  { method: 'GET', path: '/api/system/audit-logs', page: '系统监控（审核审计摘要）', group: 'new' }
]
