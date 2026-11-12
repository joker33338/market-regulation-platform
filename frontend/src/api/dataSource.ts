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
      contractMeta.value = {
        probedAt: new Date().toISOString(),
        version: doc?.info?.version || '',
        pathCount: paths.length,
        hint: hasNewRoutes
          ? `运行期 OpenAPI 返回 ${paths.length} 条路径，v0.2.2 契约已加载`
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
  { priority: 'P0', api: 'POST /api/review/{parse_id}/approve', usage: '审核通过', impact: '审核中心「审核通过」按钮禁用' },
  { priority: 'P0', api: 'POST /api/review/{parse_id}/reject', usage: '退回重新解析', impact: '审核中心「退回」按钮禁用' },
  { priority: 'P0', api: 'POST /api/review/{parse_id}/mark-error', usage: '标记识别错误', impact: '审核中心「标记错误」按钮禁用' },
  { priority: 'P0', api: 'POST /api/review/{parse_id}/save-revision', usage: '保存人工修订（含审计留痕）', impact: '审核中心「保存修订」按钮禁用' },
  { priority: 'P1', api: 'POST /api/ingestion/batches', usage: '正式入库批次 / 批次授权', impact: '入库页「发起入库批次」禁用' },
  { priority: 'P1', api: 'POST /api/ingestion/publish、/rollback', usage: 'ACTIVE 发布与回滚', impact: '入库页不开放发布/回滚' },
  { priority: 'P1', api: 'GET /api/parse/tasks/{task_id}/logs', usage: '结构化解析阶段日志', impact: '解析中心日志仅能展示 public(task) 真实字段' },
  { priority: 'P1', api: 'GET /api/system/resources、/api-logs、/error-logs、/audit-logs', usage: '资源与三类日志', impact: '系统监控相关卡片显示「未接入」空态' }
]
