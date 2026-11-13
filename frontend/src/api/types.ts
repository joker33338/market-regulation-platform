/**
 * v0.2.2 前后端契约类型
 *
 * 事实来源（不猜测接口）：
 *  - 运行期 GET /api/openapi.json 的实测路径与 schema（离线快照仅作源码参考）
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

/** 本地明确不可重试的状态：进行中无需重试，已成功完成无需重复处理 */
const NON_RETRYABLE_TASK_STATUS = ['completed', 'queued', 'pending', 'running', 'processing']

/**
 * v0.2.3 draft-4 修正：终止态 ≠ 不可恢复。
 * failed / partial / canceled / timed_out 都是终止态，但后端 POST /api/parse/tasks/{id}/resume
 * 可能允许恢复；是否可重试由后端逐请求判定（409 / 422 如实提示），前端不凭本地状态表锁死。
 * 列表「重试」与抽屉「重试任务」共用此规则，避免两处口径不一致。
 */
export function canRetryStatus(status: string): boolean {
  return !NON_RETRYABLE_TASK_STATUS.includes(status)
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
  /** v0.2.3 draft-4：文件完成度（总数 / 终止 / 成功 / 失败与完成比），不是 OCR 阶段进度 */
  workload?: TaskWorkload | null
  current_step?: string | null
  owner_id?: string | null
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
  /** v0.2.3 draft-4 新增筛选；仅运行期能力声明包含时才随请求发送，否则保持 undefined */
  kbVersion?: string
  issuingAuthority?: string
  effectiveStatus?: string
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
  /** v0.2.3 draft-4：后端实际生效的筛选（kb_version / issuing_authority / effective_status） */
  applied_filters?: Record<string, string>
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
 * （draft-2 阶段源码快照；当前契约版本与路径数以运行期探测为准）。
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
  /** v0.2.3 draft-4：服务端权限口径（ADMIN 为全量）；缺失时按空处理，不推断 */
  permissions?: string[]
  /** v0.2.3 draft-4：scoped | all；仅展示用，不作为放宽依据 */
  data_scope?: string
  /** v0.2.3 draft-4 兼容保留的旧字段；空列表不否定 ADMIN 删除权 */
  document_delete_owner_scopes?: string[]
}

/** draft-4 会话类型：账号密码登录签发的短期 Bearer，或沿用既有独立 Token */
export type AuthMode = 'password' | 'token'

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

/* ─────────────── v0.2.3 draft-4：账号密码、管理员账号、能力声明与运行日志 ───────────────
 * 依据 docs/integration/frontend-openapi-v023-draft4.json
 * （info.version=0.2.3-dev / 46 路径 / backend handoff e24cbad）。
 * 关键口径变化（覆盖 draft-2 旧设计）：
 *  - ADMIN 拥有全部业务权限（all_permissions）；不再要求 ADMIN 额外塞入 REVIEWER；
 *  - 新增账号密码登录 POST /api/auth/login（匿名）与服务端会话撤销 POST /api/auth/logout；
 *  - 新增管理员账号管理与账号事件审计、GET /api/system/capabilities 能力声明；
 *  - 新增 API / 错误日志、任务阶段日志、入库批次 / 预检 / 发布 / 回滚、检索新筛选。
 * 源码契约已交付 ≠ 运行期可用：调用方必须先经 hasRuntimeMethod() 门控；
 * 活动实例以运行期契约探测为准；源码契约已交付不等于运行期已加载，未加载时对应能力保持禁用 / 空态。
 * ------------------------------------------------------------------ */

export interface LoginRequest {
  username: string
  password: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
  expires_in: number
  principal: PrincipalInfo
}

export interface LogoutResponse {
  revoked: boolean
}

export interface RoleDefinition {
  role: PrincipalRole
  label: string
  data_scope: string
  review_write: boolean
  account_management: boolean
}

export interface RoleCatalog {
  admin_policy: string
  list: RoleDefinition[]
  safety_gates: string[]
}

/** 管理员账号（无密码 / 哈希字段，后端不回显） */
export interface AccountView {
  username: string
  principal_id: string
  owner_id: string | null
  roles: PrincipalRole[]
  review_owner_scopes: string[]
  document_delete_owner_scopes: string[]
  credential_status: CredentialStatus
}

export interface AccountCreate {
  username: string
  password: string
  owner_id?: string | null
  roles?: PrincipalRole[]
  review_owner_scopes?: string[]
}

export interface AccountUpdate {
  roles?: PrincipalRole[] | null
  review_owner_scopes?: string[] | null
  credential_status?: CredentialStatus | null
  password?: string | null
}

export type AccountPage = ListResponse<AccountView>

export interface AccountEvent {
  event_id: string
  timestamp: string
  operator_id: string
  target_id: string
  action: string
  roles: PrincipalRole[]
  credential_status: string
  before: AccountView | null
  after: AccountView | null
  password_changed: boolean
}

export type AccountEventPage = ListResponse<AccountEvent>

/* ─────────────── 能力声明（GET /api/system/capabilities） ─────────────── */

export interface PasswordCapability {
  implemented: boolean
  configured: boolean
  registration: string
}

export interface ReviewCapability {
  implemented: boolean
  ledger_configured: boolean
  per_object_gate: boolean
}

export interface IngestionCapability {
  document_types: string[]
  review_required: boolean
  quality_required: boolean
  manual_revision_export: boolean
  auto_publish: boolean
  admin_required: boolean
  write_configured: boolean
}

export interface TaskLogCapability {
  historical_backfill: boolean
  source: string
}

export interface OperationalLogCapability {
  request_bodies: boolean
  credentials: boolean
  historical_backfill: boolean
}

export interface CapabilitiesResponse {
  contract_version: string
  admin_policy: string
  identity: PrincipalInfo
  password_login: PasswordCapability
  review: ReviewCapability
  document_filters: string[]
  search_filters: string[]
  search_version_scope: string
  ingestion: IngestionCapability
  task_logs: TaskLogCapability
  operational_logs: OperationalLogCapability
}

/* ─────────────── 运行日志（API 日志 / 错误日志 / 任务阶段日志） ─────────────── */

export interface LogQuery extends PageQuery {
  /** ISO 8601 带时区闭区间；仅运行期契约支持时发送 */
  dateFrom?: string
  dateTo?: string
  /** api-logs / error-logs 专用：info | warning | error */
  level?: string
}

export interface OperationalLog {
  event_id: string
  timestamp: string
  /** 未确认身份的请求为 null；不把猜测账号写成实际人员 */
  principal_id: string | null
  actor_confirmed: boolean
  method: string
  route: string
  status_code: number
  duration_ms: number
  level: string
}

export interface OperationalLogPage {
  list: OperationalLog[]
  total: number
  page: number
  page_size: number
  source: string
  scope: string
  historical_backfill: boolean
  truncated: boolean
}

export interface TaskStageFile {
  file_id: string
  status: string
  error_code: string | null
}

export interface TaskStageEvent {
  event_id: string
  timestamp: string
  kind: string
  status: string
  files: TaskStageFile[]
}

export interface TaskLogPage {
  list: TaskStageEvent[]
  total: number
  page: number
  page_size: number
  source: string
  /** available=false 且 reason=historical_events_not_recorded：历史未记录，不回填 */
  available: boolean
  reason: string | null
  historical_backfill: boolean
  truncated: boolean
  recording_started_at: string | null
}

/* ─────────────── 入库批次 / 发布 / 回滚（draft-4） ─────────────── */

export interface IngestionDocument {
  parse_id: string
  law_name: string
  law_id: string
  expected_review_version: number
}

export interface IngestionBatchRequest {
  kb_version: string
  documents: IngestionDocument[]
  full_snapshot?: boolean
}

export interface PrecheckItem {
  parse_id: string
  review_version: number
  chunk_count: number
  quality_passed: boolean | null
  eligible: boolean
  error_code: string | null
}

export interface PrecheckResponse {
  eligible: boolean
  documents: PrecheckItem[]
  active_version: string | null
  target_exists: boolean
  write_performed: boolean
  publish_authorized: boolean
}

export interface VersionCheckResponse {
  kb_version: string
  status: string
  base_version: string | null
  active_version: string | null
  is_active: boolean
  base_matches_active: boolean
  publish_eligible: boolean
  rollback_eligible: boolean
  write_performed: boolean
  publish_authorized: boolean
}

export interface ReleaseRequest {
  kb_version: string
  /** 初次发布为 null；与当前 ACTIVE 不一致返回 409 */
  expected_active_version: string | null
}

/** 入库 / 发布 / 回滚操作回执（KnowledgeOperation） */
export interface KnowledgeOperation {
  operation_id: string
  operator_id: string
  action: string
  kb_version: string
  status: string
  created_at: string
  completed_at: string | null
  write_performed: boolean | null
  publish_authorized: boolean
  result: Record<string, unknown> | null
  error_code: string | null
  event_id: string | null
  execution_live: boolean
  outcome_unconfirmed: boolean
  [key: string]: unknown
}

export type KnowledgeOperationPage = ListResponse<KnowledgeOperation>

/** v0.2.3 draft-4：任务列表 / 详情新增的文件完成度口径（非 OCR 内部阶段百分比） */
export interface TaskWorkload {
  unit: 'files'
  total: number
  terminal: number
  succeeded: number
  failed: number
  completion_ratio: number | null
  scope: string
}
