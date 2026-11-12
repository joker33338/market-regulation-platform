import client from './client'
import type {
  ReviewActionBody, ReviewReceipt, ReviewEvent, ProcessResources,
  AuditLogItem, AuditAction, ListResponse
} from './types'

/**
 * v0.2.3 新增接口 —— 唯一依据 docs/integration/frontend-openapi-v023.json
 * （info.version=0.2.3-dev / x-contract-version=frontend-api-v0.2.3-draft-1 / 29 路径）
 *
 * 硬边界：
 *  - 源码契约已交付 ≠ 运行期可用。调用方必须先经 dataSource.hasRuntimeRoutes() 判定；
 *    审核写操作还须详情 review_write_supported=true 且 review_ledger.available=true。
 *  - 正式 8180 当前仍是 0.2.2-api-candidate / 22 路径，本模块所有接口在那里都是 404，
 *    因此页面不得提前解锁按钮，也不得以本地状态模拟写入成功。
 *  - 请求只发契约允许的字段；body 公共字段 base_result_id 必须等于路径 parse_id。
 *  - 写操作必带 Idempotency-Key（1–128 字符）：同键同请求返回原回执，同键异请求 409。
 *  - 修订正文是人工输入的不可信文本，调用方一律纯文本渲染，禁止 v-html。
 *  - 操作者由 Token→owner 映射决定，客户端不传 operator；不授予发布权限、不创建解析任务。
 */
function signalOf(signal?: AbortSignal) {
  return signal ? { signal } : {}
}

/** 每次打开操作弹窗生成一个键；失败重试沿用同一键与同一 body，避免误触发同键异请求 409 */
export function newIdempotencyKey(): string {
  try {
    if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
      return crypto.randomUUID()
    }
  } catch {
    /* 降级到时间戳 + 随机串 */
  }
  return `mrp-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 14)}`
}

type ActionName = 'approve' | 'reject' | 'mark-error' | 'save-revision'

function postReviewAction(
  parseId: string,
  action: ActionName,
  body: ReviewActionBody,
  idempotencyKey: string,
  signal?: AbortSignal
): Promise<ReviewReceipt> {
  return client
    .post<ReviewReceipt>(`/api/review/${encodeURIComponent(parseId)}/${action}`, body, {
      headers: { 'Idempotency-Key': idempotencyKey },
      ...signalOf(signal)
    })
    .then((r) => r.data)
}

/** POST /api/review/{parse_id}/approve —— reason 可选；只记录通过，不授予发布权限 */
export function approveReview(
  parseId: string,
  expectedVersion: number,
  idempotencyKey: string,
  reason?: string,
  signal?: AbortSignal
): Promise<ReviewReceipt> {
  const body: ReviewActionBody = { base_result_id: parseId, expected_version: expectedVersion }
  if (reason) body.reason = reason
  return postReviewAction(parseId, 'approve', body, idempotencyKey, signal)
}

/** POST /api/review/{parse_id}/reject —— reason 必填；后端不自动创建解析任务 */
export function rejectReview(
  parseId: string,
  expectedVersion: number,
  reason: string,
  idempotencyKey: string,
  signal?: AbortSignal
): Promise<ReviewReceipt> {
  return postReviewAction(
    parseId, 'reject',
    { base_result_id: parseId, expected_version: expectedVersion, reason },
    idempotencyKey, signal
  )
}

/** POST /api/review/{parse_id}/mark-error —— reason、page 必填；span 可选 */
export function markReviewError(
  parseId: string,
  expectedVersion: number,
  reason: string,
  page: number,
  span: string | undefined,
  idempotencyKey: string,
  signal?: AbortSignal
): Promise<ReviewReceipt> {
  const body: ReviewActionBody = {
    base_result_id: parseId, expected_version: expectedVersion, reason, page
  }
  if (span) body.span = span
  return postReviewAction(parseId, 'mark-error', body, idempotencyKey, signal)
}

/** POST /api/review/{parse_id}/save-revision —— page、content 必填；每次追加新 revision_id */
export function saveReviewRevision(
  parseId: string,
  expectedVersion: number,
  page: number,
  content: string,
  idempotencyKey: string,
  signal?: AbortSignal
): Promise<ReviewReceipt> {
  return postReviewAction(
    parseId, 'save-revision',
    { base_result_id: parseId, expected_version: expectedVersion, page, content },
    idempotencyKey, signal
  )
}

/** GET /api/review/{parse_id}/events —— 本对象真实追加事件，owner 隔离 */
export function getReviewEvents(
  parseId: string,
  q: { page: number; pageSize: number },
  signal?: AbortSignal
): Promise<ListResponse<ReviewEvent>> {
  return client
    .get<ListResponse<ReviewEvent>>(`/api/review/${encodeURIComponent(parseId)}/events`, {
      params: { page: q.page, page_size: q.pageSize },
      ...signalOf(signal)
    })
    .then((r) => r.data)
}

/** GET /api/system/resources —— 仅 API 进程真实采样；失败时 available=false 且指标为 null */
export function getProcessResources(signal?: AbortSignal): Promise<ProcessResources> {
  return client
    .get<ProcessResources>('/api/system/resources', signalOf(signal))
    .then((r) => r.data)
}

/** GET /api/system/audit-logs —— 仅本 owner 审核摘要，不含修订正文 */
export function getAuditLogs(
  q: { page: number; pageSize: number; action?: AuditAction | '' },
  signal?: AbortSignal
): Promise<ListResponse<AuditLogItem>> {
  return client
    .get<ListResponse<AuditLogItem>>('/api/system/audit-logs', {
      params: {
        page: q.page,
        page_size: q.pageSize,
        action: q.action || undefined
      },
      ...signalOf(signal)
    })
    .then((r) => r.data)
}
