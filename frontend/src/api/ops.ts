import { ref } from 'vue'
import client from './client'
import { contractState, hasRuntimeMethod } from './dataSource'
import { onAuthStateChange } from './authEvents'
import type {
  CapabilitiesResponse, IngestionBatchRequest, KnowledgeOperation,
  KnowledgeOperationPage, LogQuery, OperationalLogPage, PrecheckResponse,
  ReleaseRequest, TaskLogPage, VersionCheckResponse
} from './types'

/**
 * v0.2.3 draft-4 能力声明 / 运行日志 / 入库链路接口
 * （契约源：frontend-openapi-v023-draft4.json，backend handoff e24cbad）
 *
 * - GET /api/system/capabilities：当前身份权限、真实实现能力与登录 / 写入配置状态；
 *   configured 不等于数据库健康，write_configured 不等于已启用。
 * - GET /api/system/api-logs、/api/system/error-logs：USER / REVIEWER 本人请求，ADMIN 全部；
 *   只查最近 10000 条窗口，truncated 如实显示；不含 Authorization、查询串、正文或用户路径。
 * - GET /api/parse/tasks/{task_id}/logs：真实保存过的状态变化与文件状态；
 *   历史未记录返回 available=false / reason=historical_events_not_recorded，不回填。
 * - 入库：precheck（只读 200 可 eligible=false）/ batches（ADMIN + Idempotency-Key，同步构建
 *   201 STAGED 不自动发布）/ version-check（只读）/ publish、rollback（ADMIN + expected_active_version）。
 *
 * 运行期门控：8180 正式实例仍为 v0.2.2，以上路由均未加载；调用方必须先经
 * hasRuntimeMethod() 判定，未加载时保持禁用 / 空态，不发请求、不伪造结果。
 */

function signalOf(signal?: AbortSignal) {
  return signal ? { signal } : {}
}

function logParams(q: LogQuery) {
  return {
    page: q.page,
    page_size: q.pageSize,
    // 日期区间必须带时区；level 仅 info | warning | error，空值不发送
    date_from: q.dateFrom || undefined,
    date_to: q.dateTo || undefined,
    level: q.level || undefined
  }
}

/* ───────────── 能力声明（共享缓存：契约就绪且路由存在时加载一次） ───────────── */

export const runtimeCapabilities = ref<CapabilitiesResponse | null>(null)
export const capabilitiesState = ref<'idle' | 'loading' | 'ready' | 'error'>('idle')

/** 契约就绪且声明了 /api/system/capabilities 才加载；失败置 error，不伪造能力 */
export async function loadCapabilities(force = false): Promise<CapabilitiesResponse | null> {
  if (!force && runtimeCapabilities.value) return runtimeCapabilities.value
  if (!hasRuntimeMethod('GET', '/api/system/capabilities')) return null
  capabilitiesState.value = 'loading'
  try {
    const res = await client.get<CapabilitiesResponse>('/api/system/capabilities')
    runtimeCapabilities.value = res.data
    capabilitiesState.value = 'ready'
    return res.data
  } catch {
    capabilitiesState.value = 'error'
    return null
  }
}

/**
 * 检索新筛选（kb_version / issuing_authority / effective_status）是否被运行期声明。
 * 兼容后端以 snake_case 或 camelCase 声明字段名；未声明一律返回 false，不提前开放参数。
 */
export function searchFilterEnabled(field: string): boolean {
  const list = runtimeCapabilities.value?.search_filters
  if (contractState.value !== 'ready' || !Array.isArray(list)) return false
  const camel = field.replace(/_([a-z])/g, (_, c: string) => c.toUpperCase())
  return list.includes(field) || list.includes(camel)
}

/** 凭证失效 / 角色撤销：能力缓存必须一并清除，避免沿用上一位登录者的能力声明 */
onAuthStateChange((status) => {
  if (status === 401 || status === 403) {
    runtimeCapabilities.value = null
    capabilitiesState.value = 'idle'
  }
})

/* ───────────── 运行日志 ───────────── */

/** GET /api/system/api-logs */
export function listApiLogs(q: LogQuery, signal?: AbortSignal): Promise<OperationalLogPage> {
  return client
    .get<OperationalLogPage>('/api/system/api-logs', { params: logParams(q), ...signalOf(signal) })
    .then((r) => r.data)
}

/** GET /api/system/error-logs（只含 HTTP 4xx/5xx，不含堆栈与请求正文） */
export function listErrorLogs(q: LogQuery, signal?: AbortSignal): Promise<OperationalLogPage> {
  return client
    .get<OperationalLogPage>('/api/system/error-logs', { params: logParams(q), ...signalOf(signal) })
    .then((r) => r.data)
}

/** GET /api/parse/tasks/{task_id}/logs */
export function getTaskLogs(
  taskId: string,
  q: LogQuery,
  signal?: AbortSignal
): Promise<TaskLogPage> {
  return client
    .get<TaskLogPage>(`/api/parse/tasks/${encodeURIComponent(taskId)}/logs`, {
      params: logParams(q),
      ...signalOf(signal)
    })
    .then((r) => r.data)
}

/* ───────────── 入库链路（draft-4；写接口一律 ADMIN + Idempotency-Key） ───────────── */

/** POST /api/ingestion/precheck —— 只读逐项 eligible / error_code / quality_passed */
export function ingestionPrecheck(
  body: IngestionBatchRequest,
  signal?: AbortSignal
): Promise<PrecheckResponse> {
  return client
    .post<PrecheckResponse>('/api/ingestion/precheck', body, signalOf(signal))
    .then((r) => r.data)
}

/** POST /api/ingestion/batches —— ADMIN；必需 Idempotency-Key；同键同请求复用回执 */
export function createIngestionBatch(
  body: IngestionBatchRequest,
  idempotencyKey: string,
  signal?: AbortSignal
): Promise<KnowledgeOperation> {
  return client
    .post<KnowledgeOperation>('/api/ingestion/batches', body, {
      headers: { 'Idempotency-Key': idempotencyKey },
      ...signalOf(signal)
    })
    .then((r) => r.data)
}

/** GET /api/ingestion/batches —— ADMIN 全部，其他身份仅本人历史 */
export function listIngestionBatches(
  q: { page: number; pageSize: number },
  signal?: AbortSignal
): Promise<KnowledgeOperationPage> {
  return client
    .get<KnowledgeOperationPage>('/api/ingestion/batches', {
      params: { page: q.page, page_size: q.pageSize },
      ...signalOf(signal)
    })
    .then((r) => r.data)
}

/** GET /api/ingestion/batches/{batch_id} —— 回执、阶段摘要、execution_live、outcome_unconfirmed */
export function getIngestionBatch(batchId: string, signal?: AbortSignal): Promise<KnowledgeOperation> {
  return client
    .get<KnowledgeOperation>(`/api/ingestion/batches/${encodeURIComponent(batchId)}`, signalOf(signal))
    .then((r) => r.data)
}

/** GET /api/ingestion/version-check?kb_version= —— 只读技术条件（eligible ≠ 授权发布） */
export function ingestionVersionCheck(kbVersion: string, signal?: AbortSignal): Promise<VersionCheckResponse> {
  return client
    .get<VersionCheckResponse>('/api/ingestion/version-check', {
      params: { kb_version: kbVersion },
      ...signalOf(signal)
    })
    .then((r) => r.data)
}

/** POST /api/ingestion/publish —— ADMIN；必填 expected_active_version（初次 null）+ 幂等键 */
export function publishKbVersion(
  body: ReleaseRequest,
  idempotencyKey: string,
  signal?: AbortSignal
): Promise<KnowledgeOperation> {
  return client
    .post<KnowledgeOperation>('/api/ingestion/publish', body, {
      headers: { 'Idempotency-Key': idempotencyKey },
      ...signalOf(signal)
    })
    .then((r) => r.data)
}

/** POST /api/ingestion/rollback —— ADMIN；目标须 ARCHIVED；相同幂等要求 */
export function rollbackKbVersion(
  body: ReleaseRequest,
  idempotencyKey: string,
  signal?: AbortSignal
): Promise<KnowledgeOperation> {
  return client
    .post<KnowledgeOperation>('/api/ingestion/rollback', body, {
      headers: { 'Idempotency-Key': idempotencyKey },
      ...signalOf(signal)
    })
    .then((r) => r.data)
}
