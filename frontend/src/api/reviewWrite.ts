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

/** 每个「新操作」生成一个键；同一次结果未确认的重试沿用同一键与同一 body */
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

export type ReviewActionName = 'approve' | 'reject' | 'mark-error' | 'save-revision'

/**
 * 统一写入出口：调用方传入「已冻结」的 body 快照。
 * 写入结果未确认时，重试必须复用同一 action / parseId / body / Idempotency-Key，
 * 否则后端按同键异请求返回 409 idempotency_conflict。
 * body 由调用方在首次提交时构造一次，后续不从可编辑表单重新读取。
 */
export function postReviewAction(
  parseId: string,
  action: ReviewActionName,
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

/** 首次提交时从可编辑表单取一次值；构造出 body 快照后，重试不再读取表单 */
export interface ReviewActionInput {
  reason?: string
  page?: number
  span?: string
  content?: string
}

/**
 * 按 action 构造契约允许的 body 快照（唯一构造点）。
 * 不传契约外字段、不指定 operator；修订正文原样保留前导空格与换行，不 trim。
 * 结果未确认的重试必须复用返回的同一个对象，避免同键异请求 409。
 */
export function makeReviewActionBody(
  action: ReviewActionName,
  parseId: string,
  expectedVersion: number,
  input: ReviewActionInput
): ReviewActionBody {
  const body: ReviewActionBody = { base_result_id: parseId, expected_version: expectedVersion }
  if (action === 'approve') {
    if (input.reason) body.reason = input.reason // 可选备注，空串不发送
  } else if (action === 'reject') {
    if (input.reason !== undefined) body.reason = input.reason // 必填，由表单校验保证非空
  } else if (action === 'mark-error') {
    if (input.reason !== undefined) body.reason = input.reason
    if (input.page !== undefined) body.page = input.page
    if (input.span) body.span = input.span
  } else {
    if (input.page !== undefined) body.page = input.page
    if (input.content !== undefined) body.content = input.content
  }
  return body
}

/** POST /api/review/{parse_id}/approve —— reason 可选；只记录通过，不授予发布权限 */
export function approveReview(
  parseId: string,
  expectedVersion: number,
  idempotencyKey: string,
  reason?: string,
  signal?: AbortSignal
): Promise<ReviewReceipt> {
  const body = makeReviewActionBody('approve', parseId, expectedVersion, { reason })
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
  const body = makeReviewActionBody('reject', parseId, expectedVersion, { reason })
  return postReviewAction(parseId, 'reject', body, idempotencyKey, signal)
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
  const body = makeReviewActionBody('mark-error', parseId, expectedVersion, { reason, page, span })
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
  const body = makeReviewActionBody('save-revision', parseId, expectedVersion, { page, content })
  return postReviewAction(parseId, 'save-revision', body, idempotencyKey, signal)
}

/**
 * GET /api/review/{parse_id}/events —— 本对象真实追加事件，owner 隔离。
 * 原样返回后端结构：body 外层是完整回执，content/reason/page/span 在必填的
 * event.request 内。这里刻意不做扁平映射，避免掩盖层级差异或伪造修订来源。
 */
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
