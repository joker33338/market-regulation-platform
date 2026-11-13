import client from './client'
import type {
  DocumentInfo, DocumentList, DocumentQuery, ParseHistory, TaskList, TaskQuery,
  ReviewQueue, ReviewDetail, PreviewRequest, PreviewResponse,
  KbVersionList, VersionInfo, SearchRequest, SearchResponse,
  StatsResponse, HealthResponse, RuntimeOpenApi
} from './types'

/**
 * v0.2.2 只读接口 —— 路径以运行期 GET /api/openapi.json 实测为准，离线快照仅作源码参考
 * 与 docs/integration/frontend-api-contract.md。复用 parse.ts 的 9 个既有接口，不重复定义。
 *
 * 约定：
 *  - 所有函数接受可选 AbortSignal，页面切换 / 卸载可取消请求
 *  - 列表统一 {list,total,page,page_size,source}；page 从 1，page_size 1–100
 *  - 不传后端不支持的筛选字段（额外 JSON 字段会 422）
 *  - 身份 ID 不推导：source_file_id / 任务文件 ID / database_parse_id 各司其职
 *  - 运行期是否可用由 GET /api/openapi.json 探测，本文件不假设 8180 已加载新路由
 */

function signalOf(signal?: AbortSignal) {
  return signal ? { signal } : {}
}

/* ───────────── 文档管理 ───────────── */

/** GET /api/documents */
export function listDocuments(q: DocumentQuery, signal?: AbortSignal): Promise<DocumentList> {
  return client
    .get<DocumentList>('/api/documents', {
      params: {
        page: q.page,
        page_size: q.pageSize,
        keyword: q.keyword || undefined,
        status: q.status || undefined,
        doc_type: q.docType || undefined,
        // v0.2.3 新增；调用方须先确认运行期契约具备这些参数，未确认时字段保持 undefined（不发送）
        date_from: q.dateFrom || undefined,
        date_to: q.dateTo || undefined,
        sort_by: q.sortBy || undefined,
        order: q.order || undefined
      },
      ...signalOf(signal)
    })
    .then((r) => r.data)
}

/** GET /api/documents/{file_id} */
export function getDocument(fileId: string, signal?: AbortSignal): Promise<DocumentInfo> {
  return client
    .get<DocumentInfo>(`/api/documents/${encodeURIComponent(fileId)}`, signalOf(signal))
    .then((r) => r.data)
}

/** GET /api/documents/{file_id}/parse-history */
export function getDocumentHistory(
  fileId: string,
  q: { page: number; pageSize: number },
  signal?: AbortSignal
): Promise<ParseHistory> {
  return client
    .get<ParseHistory>(`/api/documents/${encodeURIComponent(fileId)}/parse-history`, {
      params: { page: q.page, page_size: q.pageSize },
      ...signalOf(signal)
    })
    .then((r) => r.data)
}

/**
 * DELETE /api/documents/{file_id} —— 文档删除（当前后端契约未声明，调用方必须先经方法级门控）
 *
 * 只有在运行期 GET /api/openapi.json 确实声明 DELETE 该方法时，页面才会解锁按钮并调用本函数。
 * 删除结果以后端真实响应为准：成功只代表请求被接受，页面随后重新拉取列表确认，绝不本地删除行。
 */
export function deleteDocument(fileId: string, signal?: AbortSignal): Promise<Record<string, unknown>> {
  return client
    .delete<Record<string, unknown>>(`/api/documents/${encodeURIComponent(fileId)}`, signalOf(signal))
    .then((r) => r.data || {})
}

/* ───────────── 智能解析中心 ───────────── */

/** GET /api/parse/tasks —— 真实任务列表（状态枚举以返回值 status 为准，前端不创造状态） */
export function listParseTasks(q: TaskQuery, signal?: AbortSignal): Promise<TaskList> {
  return client
    .get<TaskList>('/api/parse/tasks', {
      params: {
        page: q.page,
        page_size: q.pageSize,
        status: q.status || undefined,
        engine: q.engine || undefined
      },
      ...signalOf(signal)
    })
    .then((r) => r.data)
}

/* ───────────── 文档审核（只读） ───────────── */

/** GET /api/review?requires_review=true —— 完整待复核语义队列，非 findings 级视图 */
export function listReviews(
  q: { page: number; pageSize: number; requiresReview?: boolean },
  signal?: AbortSignal
): Promise<ReviewQueue> {
  return client
    .get<ReviewQueue>('/api/review', {
      params: {
        page: q.page,
        page_size: q.pageSize,
        requires_review: q.requiresReview ?? true
      },
      ...signalOf(signal)
    })
    .then((r) => r.data)
}

/** GET /api/review/{parse_id} */
export function getReviewDetail(parseId: string, signal?: AbortSignal): Promise<ReviewDetail> {
  return client
    .get<ReviewDetail>(`/api/review/${encodeURIComponent(parseId)}`, signalOf(signal))
    .then((r) => r.data)
}

/* ───────────── Chunk / 结构预览（不入库、不审核） ───────────── */

/** POST /api/parse/tasks/{task_id}/files/{file_id}/preview */
export function previewTaskFile(
  taskId: string,
  fileId: string,
  body: PreviewRequest,
  signal?: AbortSignal
): Promise<PreviewResponse> {
  return client
    .post<PreviewResponse>(
      `/api/parse/tasks/${encodeURIComponent(taskId)}/files/${encodeURIComponent(fileId)}/preview`,
      body,
      signalOf(signal)
    )
    .then((r) => r.data)
}

/** POST /api/review/{parse_id}/preview —— 已持久化结果的同一预览器 */
export function previewReviewResult(
  parseId: string,
  body: PreviewRequest,
  signal?: AbortSignal
): Promise<PreviewResponse> {
  return client
    .post<PreviewResponse>(`/api/review/${encodeURIComponent(parseId)}/preview`, body, signalOf(signal))
    .then((r) => r.data)
}

/* ───────────── public 知识库版本（只读，绝不读 mvp_test_*） ───────────── */

/** GET /api/knowledge/versions */
export function listKbVersions(
  q: { page: number; pageSize: number },
  signal?: AbortSignal
): Promise<KbVersionList> {
  return client
    .get<KbVersionList>('/api/knowledge/versions', {
      params: { page: q.page, page_size: q.pageSize },
      ...signalOf(signal)
    })
    .then((r) => r.data)
}

/** GET /api/knowledge/versions/{version} */
export function getKbVersion(version: string, signal?: AbortSignal): Promise<VersionInfo> {
  return client
    .get<VersionInfo>(`/api/knowledge/versions/${encodeURIComponent(version)}`, signalOf(signal))
    .then((r) => r.data)
}

/* ───────────── 法规检索（仅 public ACTIVE，无 AI 问答） ───────────── */

/**
 * POST /api/knowledge/search —— 基础仅 query/mode/limit；
 * v0.2.3 draft-4 新增 kb_version / issuing_authority / effective_status，
 * 仅在调用方确认运行期能力（capabilities.search_filters）包含时才传入，否则字段不发送（额外字段 422）。
 */
export function searchKnowledge(body: SearchRequest, signal?: AbortSignal): Promise<SearchResponse> {
  // 请求体键名与后端契约一致（snake_case）；未确认支持的筛选不进入 payload
  const payload: Record<string, unknown> = {
    query: body.query,
    mode: body.mode,
    limit: body.limit
  }
  if (body.kbVersion) payload.kb_version = body.kbVersion
  if (body.issuingAuthority) payload.issuing_authority = body.issuingAuthority
  if (body.effectiveStatus) payload.effective_status = body.effectiveStatus
  return client
    .post<SearchResponse>('/api/knowledge/search', payload, signalOf(signal))
    .then((r) => r.data)
}

/* ───────────── 首页统计 / 系统监控 ───────────── */

/** GET /api/stats/overview?days=14 —— 三种来源范围不同，禁止相加 */
export function getStatsOverview(days = 14, signal?: AbortSignal): Promise<StatsResponse> {
  return client
    .get<StatsResponse>('/api/stats/overview', { params: { days }, ...signalOf(signal) })
    .then((r) => r.data)
}

/** GET /api/system/health —— 只有真实只读查询成功才标记 ONLINE */
export function getSystemHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return client.get<HealthResponse>('/api/system/health', signalOf(signal)).then((r) => r.data)
}

/* ───────────── 运行期契约探测 ───────────── */

/**
 * GET /api/openapi.json（需 Bearer Token；匿名 /openapi.json 后端显式关闭）
 * 用于判定活动实例是否已加载 v0.2.2 路由，绝不用离线快照冒充运行期成功。
 */
export function getRuntimeOpenApi(signal?: AbortSignal): Promise<RuntimeOpenApi> {
  return client.get<RuntimeOpenApi>('/api/openapi.json', signalOf(signal)).then((r) => r.data)
}
