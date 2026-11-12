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
  /** v0.2.3：ISO 8601 且必须带时区；仅运行期契约具备 date_from/date_to 时才发送 */
  dateFrom?: string
  dateTo?: string
  /** v0.2.3 白名单，后端不接受其它值 */
  sortBy?: 'uploaded_at' | 'file_name' | 'size_bytes' | 'status' | ''
  order?: 'asc' | 'desc' | ''
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
  /** v0.2.3 起由后端按台账可用性 + owner 写授权动态返回；v0.2.2 恒为 false */
  review_write_supported: boolean
  /** v0.2.3 审核台账；v0.2.2 无此字段，前端按缺失处理，不推断为可用 */
  review_ledger?: ReviewLedger | null
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
    /** v0.2.3：不可用时后端给出原因，成功为 null；不得把不可用显示成 0 */
    reason?: string | null
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
  info: { title?: string; version?: string; 'x-contract-version'?: string }
  paths: Record<string, unknown>
}

/* ─────────────── v0.2.3 draft-2 身份、审核台账与监控 ───────────────
 * 依据 docs/integration/frontend-openapi-v023-draft2.json
 * （info.version=0.2.3-dev / x-contract-version=frontend-api-v0.2.3-draft-2 / 30 路径）。
 * 相对 draft-1 的关键变化：新增 GET /api/auth/me；principal_id（实际登录人员）
 * 与 owner_id（业务数据归属）分离；roles 为 USER/REVIEWER/ADMIN，ADMIN 不隐含 REVIEWER；
 * 写授权由 review_owner_scopes + 后端逐请求校验决定，旧 owner→writers 说明已不适用。
 * 源码契约已交付 ≠ 运行期可用：调用方必须先经 hasRuntimeRoutes() 门控，
 * 审核写操作还要求详情 review_write_supported=true 且 review_ledger.available=true。
 * ------------------------------------------------------------------ */

export type PrincipalRole = 'USER' | 'REVIEWER' | 'ADMIN'
export type CredentialStatus = 'active' | 'disabled' | 'revoked'

/** GET /api/auth/me：当前凭证对应的不可变身份快照；五个字段全部必填且不返回凭证 */
export interface PrincipalInfo {
  principal_id: string
  /** 业务数据归属，可为 null（纯审核员无个人 owner）；不等于实际操作者 */
  owner_id: string | null
  roles: PrincipalRole[]
  /** 允许审核写入的目标 owner 白名单；非空也不代表已获写授权，仍以后端逐请求校验为准 */
  review_owner_scopes: string[]
  credential_status: CredentialStatus
}

/** 身份字段在 draft-2 的回执/事件里可为 null：旧事件不补认具体人员 */
export interface ReviewIdentityFields {
  operator_id?: string | null
  owner_id?: string | null
  /** principal-v1 = 新身份模型；legacy-owner = 历史 owner 别名，前端不得推导人员 */
  identity_model?: string
}

/** GET /api/review/{parse_id} 的台账摘要；requires_review 是 OCR 来源信号，不能推导台账状态 */
export interface ReviewLedger {
  available: boolean
  reason?: string | null
  version: number
  status: 'unreviewed' | 'pending' | 'flagged' | 'rejected' | 'approved' | string
  current_revision?: string | null
}

/** POST /api/review/{parse_id}/approve|reject|mark-error|save-revision 的公共 body */
export interface ReviewActionBody {
  /** 必须等于路径 parse_id；后端拒绝不一致 */
  base_result_id: string
  /** 首次 0，之后取详情 review_ledger.version；并发/源变更返回 409 */
  expected_version: number
  reason?: string
  page?: number | null
  content?: string | null
  span?: string | null
}

/** 200 回执：write_performed 为真实写入结果，前端不自行判定成功 */
export interface ReviewReceipt extends ReviewIdentityFields {
  event_id: string
  parse_id: string
  base_result_id: string
  action: string
  /** 兼容别名（旧事件为历史 owner 值）；实际操作者以 operator_id 为准 */
  operator: string
  timestamp: string
  version: number
  revision_id: string | null
  status: string
  before: Record<string, unknown>
  write_performed: boolean
  original_result_modified: boolean
  publish_authorized: boolean
  reparse_task_created: boolean
}

/**
 * GET /api/review/{parse_id}/events 的真实追加事件（后端 OpenAPI 显式 ReviewEvent Schema）。
 *
 * 真实结构 = 完整写入回执 + 必填 request（ReviewAction，与写请求 body 同构）。
 * 正文 content / 理由 reason / 页码 page / span 只在 request 内，顶层没有这些字段。
 * 前端不做扁平映射、不从顶层猜字段、不伪造修订；修订正文一律按不可信纯文本渲染。
 */
export interface ReviewEvent extends ReviewIdentityFields {
  event_id: string
  parse_id: string
  base_result_id: string
  action: string
  /** 兼容别名；operator_id 为 null 时如实显示「未知（历史记录）」，不把 owner 补认成人员 */
  operator: string
  timestamp: string
  version: number
  status: string
  revision_id: string | null
  before: Record<string, unknown>
  write_performed: boolean
  original_result_modified: boolean
  publish_authorized: boolean
  reparse_task_created: boolean
  /** 必填：本次真实请求快照，正文 / 理由 / 页码只从此处读取 */
  request: ReviewActionBody
}

/** GET /api/system/resources：仅 API 进程真实指标，不是宿主机/GPU/利用率 */
export interface ProcessResources {
  available: boolean
  reason?: string | null
  scope?: string
  sampled_at: string
  memory_rss_bytes: number | null
  cpu_user_seconds: number | null
  cpu_system_seconds: number | null
  uptime_seconds: number | null
  threads: number | null
}

/** GET /api/system/audit-logs：按当前身份与审核范围返回的真实摘要，不含修订正文 */
export interface AuditLogItem extends ReviewIdentityFields {
  event_id: string
  parse_id?: string
  action: string
  /** 兼容别名；新事件以 operator_id / owner_id 展示实际操作者与文档所属人 */
  operator?: string
  timestamp: string
  version?: number
  [key: string]: unknown
}

export type AuditAction = 'approve' | 'reject' | 'mark-error' | 'save-revision'

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
