/**
 * v0.2.2 前后端契约类型
 *
 * 事实来源（不猜测接口）：
 *  - docs/integration/frontend-openapi.json（OpenAPI 3.1.0，0.2.2-api-candidate，22 路径 / 16 schema）
 *  - docs/integration/frontend-api-contract.md
 *  - qa_core/api/schemas.py、common.py、read_store.py、monitoring.py（只读核对）
 * 运行期是否可用由 GET /api/openapi.json 探测决定，类型存在 ≠ 服务已加载。
 */

/* ─────────────── 通用 ─────────────── */

export interface ListResponse<T> {
  list: T[]
  total: number
  page: number
  page_size: number
  source: string
}

export interface PageQuery {
  page: number
  pageSize: number
}

/* ─────────────── 复用：旧解析 API ─────────────── */

/** 任务内单文件状态（对应 mineru_api.public 的 files 项） */
export interface ParseFileItem {
  file_id: string
  file_name: string
  sha256: string
  database_parse_id?: string | null
  /** 引擎选择由后端返回，前端不得自行判断 */
  selected_engine?: string[] | string | null
  requires_review?: boolean | null
  fallback_reason?: unknown
  status: string
  error?: unknown
}

export interface ParseTask {
  task_id: string
  status: string
  mode: string
  cancel_requested: boolean
  cancel_scope?: string | null
  provider: string
  created_at: string
  completed_at?: string | null
  error?: unknown
  files: ParseFileItem[]
}

export interface UploadResponse {
  file_id: string
  sha256: string
  bytes: number
}

export interface ParseServiceInfo {
  mode: string
  provider: string
  enabled: boolean
  database_enabled: boolean
  dual_engine_enabled: boolean
}

/** POST /api/parse/tasks 请求体白名单（多传字段会被后端拒绝） */
export interface CreateTaskPayload {
  file_ids: string[]
  strategy?: 'auto' | 'local' | 'remote'
  allow_cloud_fallback?: boolean
  sensitive?: boolean
}

export interface TaskResults {
  task_id: string
  status: string
  results: Array<{ file_id: string; document: Record<string, unknown> }>
}

/** 后端任务终止态（参考 parsing_upload.html 的轮询终止条件） */
export const TERMINAL_TASK_STATUS = [
  'completed',
  'partial',
  'failed',
  'canceled',
  'timed_out'
] as const

export function isTerminalStatus(status: string): boolean {
  return (TERMINAL_TASK_STATUS as readonly string[]).includes(status)
}

/* ─────────────── 新增：文档管理 ─────────────── */

/** GET /api/documents · DocumentInfo */
export interface DocumentInfo {
  file_id: string
  file_name: string
  /** pdf | docx | image */
  doc_type: string
  size_bytes: number
  sha256: string
  uploaded_at: string
  /** upload_metadata（确证）| metadata_mtime（仅元数据修改时间，不得宣称为确证上传时间） */
  uploaded_at_source: string
  /** uploaded / pending_review 或真实任务状态；不臆造 reviewed / ingested */
  status: string
  latest_task_id: string | null
  parse_count: number
}

export type DocumentList = ListResponse<DocumentInfo>

/** GET /api/documents/{file_id}/parse-history */
export interface ParseHistoryItem {
  task: ParseTask
  /** 任务文件 ID（≠ 上传 file_id），用于 artifact / 任务 preview */
  file_id: string
  source_file_id: string
  database_parse_id: string | null
  elapsed_seconds: number | null
}
export type ParseHistory = ListResponse<ParseHistoryItem>

export interface DocumentQuery extends PageQuery {
  keyword?: string
  status?: string
  docType?: 'pdf' | 'docx' | 'image' | ''
}

/* ─────────────── 新增：任务列表 ─────────────── */

export interface FileMapping {
  file_id: string
  source_file_id: string | null
  database_parse_id: string | null
}

export type TaskSummary = ParseTask & {
  /** 仅记录过时非空；不存在确定总工作量时不得模拟进度百分比 */
  elapsed_seconds: number | null
  file_mappings: FileMapping[]
}

export type TaskList = ListResponse<TaskSummary>

export interface TaskQuery extends PageQuery {
  status?: string
  engine?: string
}

/* ─────────────── 新增：文档审核（只读） ─────────────── */

/** GET /api/review —— 基于 document_review.documents 完整语义，不依赖 v_review_queue 视图 */
export interface ReviewQueueItem {
  parse_id: string
  document_id: string
  file_name: string
  file_type: string
  parsing_status: string
  requires_review: boolean
  source_location: Record<string, unknown>
  quality: Record<string, unknown>
  imported_at: string
}
export type ReviewQueue = ListResponse<ReviewQueueItem>

export interface ReviewDetail {
  parse_id: string
  document_id: string
  file_name: string
  parsing_status: string
  requires_review: boolean
  source_location: Record<string, unknown>
  quality: Record<string, unknown>
  raw_text: string
  markdown_content: string
  /** 最终候选：含 pages / layout_blocks / tables；须作为不可信内容渲染 */
  original_result: Record<string, unknown>
  source_file_id: string | null
  task_id: string | null
  /** 本地 checkpoint 未保留或身份无法核验时为 null，不得伪造对照 */
  local_candidate: Record<string, unknown> | null
  local_candidate_available: boolean
  /** 后端恒为 false：正式审核写入未实现，四个写按钮必须禁用 */
  review_write_supported: boolean
}

/* ─────────────── 新增：Chunk 预览 / 知识库版本 ─────────────── */

export interface PreviewRequest {
  document_type: 'law' | 'case'
  max_chars?: number
}

export interface PreviewResponse {
  /** preview_chunks 输出：parents / chunks / tables / quality / warnings */
  preview: Record<string, unknown>
  /** 恒为 false —— 预览成功绝不等于正式入库成功 */
  write_performed: boolean
}

export interface KbVersionItem {
  kb_version: string
  status: string
  active: boolean
  dimension: number
  created_at: string
  stats: Record<string, unknown> | string
}
export type KbVersionList = ListResponse<KbVersionItem>
export type VersionInfo = KbVersionItem

/* ─────────────── 新增：法规检索 ─────────────── */

export interface SearchRequest {
  query: string
  mode: 'keyword' | 'hybrid'
  limit?: number
}

export interface SearchHit {
  chunk_id: string
  doc_version_id: string
  regulation_name: string
  article_no: string
  article_text: string
  chapter: string
  kb_version: string
  /** keyword_match 只表示匹配；rrf 为融合排序分，均非法律准确率 */
  raw_score: number | null
  score_kind: 'keyword_match' | 'rrf' | string
  source: Record<string, unknown>
}

export interface SearchResponse {
  /** unpublished = 正式 public 知识库尚无 ACTIVE 版本 */
  status: 'ready' | 'unpublished'
  kb_version: string | null
  mode: string
  list: SearchHit[]
  count: number
  source: string
}

/* ─────────────── 新增：统计与健康 ─────────────── */

export interface StatsResponse {
  generated_at: string
  window: { since: string; until: string }
  /** 当前用户全部上传元数据（全量） */
  uploads: { source: string; scope: string; total: number }
  /** 窗口内 SQLite 任务；不同来源不得与 uploads / parsed_documents 相加 */
  tasks: {
    source: string
    scope: string
    total: number
    status_distribution: Record<string, number>
    /** 文件引擎选择次数，不保证等于任务数 */
    engine_file_selections: Record<string, number>
    /** 真实任务创建日计数，不是处理耗时或成功数 */
    created_daily: Record<string, number>
  }
  parsed_documents: {
    source: string
    scope: string
    available: boolean
    total: number | null
    requires_review: number | null
  }
  recent_tasks: ParseTask[]
}

export interface HealthComponent {
  state: string
  check?: string
  model_ready?: boolean
  configured?: boolean
}

export interface HealthResponse {
  status: string
  components: Record<string, HealthComponent>
}

/* ─────────────── 运行期能力探测 ─────────────── */

export interface RuntimeOpenApi {
  openapi: string
  info: { title?: string; version?: string }
  paths: Record<string, unknown>
}

/* ─────────────── UI 状态枚举 ─────────────── */

/** 组件五态：仅真实探测成功才允许 ONLINE */
export type ComponentState = 'ONLINE' | 'OFFLINE' | 'NOT_CONFIGURED' | 'UNKNOWN' | 'ERROR'

/** 页面统一交互状态 */
export type LoadState =
  | 'loading'
  | 'ready'
  | 'empty'
  | 'no-permission'
  | 'outdated'
  | 'unavailable'
  | 'error'

/** 数据源标记（保留用于徽章展示；v0.2.2 起页面不再渲染 DEMO 业务结果） */
export type DataSource = 'real' | 'demo'

/** @deprecated 入库批次四态 Mock 遗留类型；v0.2.2 页面已不使用，仅为隔离模块可编译保留 */
export type BatchState = '已完成' | '执行中' | '失败' | '阻塞'
