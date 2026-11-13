import type { AxiosRequestConfig } from 'axios'
import client from './client'
import { ApiError, toApiError } from './errors'
import type {
  LibraryArticleParts,
  LibraryChapterParts,
  LibraryDetail,
  LibraryDetailQuery,
  LibraryKind,
  LibraryList,
  LibraryPartsQuery,
  LibraryQuery,
  LibraryReferenceParts,
  LibraryRoute
} from './types'

/**
 * v0.2.3 draft-5 —— 法规库 / 处罚案例库 8 条只读 GET 接口。
 *
 * 事实边界：
 *  - 相对 draft-4 为纯增量 8 条 GET，无删除、无既有方法变更；CapabilitiesResponse
 *    未新增 library 字段，可用性只能由 hasRuntimeMethod('GET', path) 方法级门控决定。
 *  - 页面在路由未加载时**不调用本模块任何函数**（页面局部 useLibraryQuery 门控先行），
 *    因此本模块不做能力探测；探测结果由调用方负责。
 *  - 查询参数全部 snake_case 白名单；附加未知字段会 422。法规库绝不构造 violation 键，
 *    kb_version 只由调用方在 ADMIN 身份下传入；空值一律不发送。
 *  - 路径中的 doc_version_id / article_id 只来自列表响应的行，禁止从 URL / 拼接 / 推导。
 *  - source_url 仍需 Bearer：原件字节必须走 documentFiles.getSourceFile() 的认证
 *    ArrayBuffer → Blob URL 路径，绝不能直接塞进 iframe / img。
 *
 * 错误归一化定位（兜底，不参与页面门控 / 状态映射）：
 *  - 页面状态一律由 src/views/library/useLibraryQuery.ts 按 status + code 精确映射；
 *    门控态只由 hasToken → probeContract → hasRuntimeMethod 判定，绝不从响应 404 反推；
 *  - 本模块仅在 .catch() 内把 404 / 422 / 503 重抛为保留 status 与 code 的 ApiError，
 *    避免异常穿透到页面；hint 只是兜底文案，页面使用 Phase 2 统一文案、不展示这里原文。
 *  - 其它错误原样抛出，仍由统一错误层处理；不改 errors.ts / useAsyncData / AsyncPanel。
 */

/** 8 条 draft-5 路由（OpenAPI 模板路径，供页面展示运行期状态表与方法级门控） */
export const LIBRARY_ROUTES: readonly LibraryRoute[] = [
  { method: 'GET', path: '/api/library/laws', page: '法规库（列表）' },
  { method: 'GET', path: '/api/library/laws/{doc_version_id}', page: '法规库（详情）' },
  { method: 'GET', path: '/api/library/laws/{doc_version_id}/chapters', page: '法规库（章节）' },
  { method: 'GET', path: '/api/library/laws/{doc_version_id}/articles', page: '法规库（条款列表）' },
  { method: 'GET', path: '/api/library/laws/{doc_version_id}/articles/{article_id}', page: '法规库（条款正文）' },
  { method: 'GET', path: '/api/library/cases', page: '处罚案例库（列表）' },
  { method: 'GET', path: '/api/library/cases/{doc_version_id}', page: '处罚案例库（详情）' },
  { method: 'GET', path: '/api/library/cases/{doc_version_id}/references', page: '处罚案例库（处罚依据引用）' }
] as const

export const LIBRARY_LIST_PATHS: Record<LibraryKind, string> = {
  law: '/api/library/laws',
  case: '/api/library/cases'
}
export const LIBRARY_DETAIL_PATHS: Record<LibraryKind, string> = {
  law: '/api/library/laws/{doc_version_id}',
  case: '/api/library/cases/{doc_version_id}'
}
export const LIBRARY_CHAPTERS_PATH = '/api/library/laws/{doc_version_id}/chapters'
export const LIBRARY_ARTICLES_PATH = '/api/library/laws/{doc_version_id}/articles'
export const LIBRARY_ARTICLE_PATH = '/api/library/laws/{doc_version_id}/articles/{article_id}'
export const LIBRARY_REFERENCES_PATH = '/api/library/cases/{doc_version_id}/references'

/* 兜底文案（Phase 2 口径）：页面不展示这里的 hint，只按 status + code 取统一文案 */
const HINT_404 = '未找到该对象，或它不在当前身份的可见范围内。出于安全考虑不区分「不存在」与「无权访问」，请返回列表重新选择。'
const HINT_422 = '请求参数不被接受（422）：请检查分页与筛选参数；空值一律不发送。'
const HINT_503_SCHEMA = '已发布版本存在，但新库 Schema 未安装（library_schema_not_installed）。这不是空数据，请联系管理员完成安装后重试。'

/**
 * 兜底：把 library 接口的 404 / 422 / 503 重抛为保留 status / code 的 ApiError，
 * 仅用于避免异常穿透；页面状态不依赖这里的 kind 或 hint。
 * 其它错误原样抛出，交给统一错误层。
 */
function normalizeLibraryError(err: unknown): never {
  const e = toApiError(err)
  if (e.status === 404) {
    throw new ApiError(404, e.code, 'error', HINT_404)
  }
  if (e.status === 422) {
    const hint = e.code === 'violation_filter_case_only'
      ? '请求参数不被接受（422，violation_filter_case_only）：violation 仅案例库支持，法规库不得发送该参数。'
      : HINT_422
    throw new ApiError(422, e.code, 'error', hint)
  }
  if (e.status === 503) {
    const hint = e.code === 'library_schema_not_installed'
      ? HINT_503_SCHEMA
      : '后端服务暂不可用或请求失败：未展示任何替代数据，请稍后重试。'
    throw new ApiError(503, e.code, 'error', hint)
  }
  throw e
}

function request<T>(url: string, config: AxiosRequestConfig = {}): Promise<T> {
  return client
    .get<T>(url, config)
    .then((r) => r.data)
    .catch((err: unknown): never => normalizeLibraryError(err))
}

function signalConfig(signal?: AbortSignal): AxiosRequestConfig {
  return signal ? { signal } : {}
}

/** 白名单参数构造：undefined / null / 空串一律不进入 params（避免 422） */
function withParams(
  params: Record<string, string | number | undefined | null>,
  signal?: AbortSignal
): AxiosRequestConfig {
  const clean: Record<string, string | number> = {}
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') continue
    clean[key] = value
  }
  return { params: clean, ...signalConfig(signal) }
}

/** 截断到契约上限并去掉空值；不从本地补写任何内容 */
function bounded(value: string | undefined, max: number): string | undefined {
  if (value == null) return undefined
  const trimmed = value.trim().slice(0, max)
  return trimmed || undefined
}

function normPage(value?: number): number {
  return typeof value === 'number' && Number.isFinite(value) && value >= 1
    ? Math.min(Math.floor(value), Number.MAX_SAFE_INTEGER)
    : 1
}

/** page_size 限制 1..100，默认 20 */
function normPageSize(value?: number): number {
  if (typeof value !== 'number' || !Number.isFinite(value)) return 20
  return Math.min(Math.max(Math.floor(value), 1), 100)
}

/** 列表参数白名单；法规库连 violation 键都不构造（传了会 422 violation_filter_case_only） */
function listParams(q: LibraryQuery, kind: LibraryKind): Record<string, string | number | undefined> {
  const params: Record<string, string | number | undefined> = {
    page: normPage(q.page),
    page_size: normPageSize(q.pageSize),
    query: bounded(q.query, 200),
    kb_version: bounded(q.kbVersion, 128)
  }
  if (kind === 'case') params.violation = bounded(q.violation, 200)
  return params
}

function detailParams(q: LibraryDetailQuery = {}): Record<string, string | undefined> {
  return { kb_version: bounded(q.kbVersion, 128) }
}

/** 子列表：page / page_size 未显式给出时保持 undefined，不发送（由后端取默认值） */
function partsParams(q: LibraryPartsQuery = {}): Record<string, string | number | undefined> {
  return {
    page: q.page == null ? undefined : normPage(q.page),
    page_size: q.pageSize == null ? undefined : normPageSize(q.pageSize),
    kb_version: bounded(q.kbVersion, 128)
  }
}

function requireId(id: string, label: string): string {
  if (!id) throw new ApiError(0, '', 'error', `${label} 只能来自列表响应的行；当前为空，未发起请求`)
  return id
}

/* ───────────── 列表 ───────────── */

/** GET /api/library/laws */
export function listLibraryLaws(q: LibraryQuery = {}, signal?: AbortSignal): Promise<LibraryList> {
  return request<LibraryList>('/api/library/laws', withParams(listParams(q, 'law'), signal))
}

/** GET /api/library/cases（violation 仅案例库） */
export function listLibraryCases(q: LibraryQuery = {}, signal?: AbortSignal): Promise<LibraryList> {
  return request<LibraryList>('/api/library/cases', withParams(listParams(q, 'case'), signal))
}

/* ───────────── 详情 ───────────── */

/** GET /api/library/laws/{doc_version_id} */
export function getLibraryLaw(
  docVersionId: string,
  q: LibraryDetailQuery = {},
  signal?: AbortSignal
): Promise<LibraryDetail> {
  const id = requireId(docVersionId, 'doc_version_id')
  return request<LibraryDetail>(`/api/library/laws/${encodeURIComponent(id)}`, withParams(detailParams(q), signal))
}

/** GET /api/library/cases/{doc_version_id} */
export function getLibraryCase(
  docVersionId: string,
  q: LibraryDetailQuery = {},
  signal?: AbortSignal
): Promise<LibraryDetail> {
  const id = requireId(docVersionId, 'doc_version_id')
  return request<LibraryDetail>(`/api/library/cases/${encodeURIComponent(id)}`, withParams(detailParams(q), signal))
}

/* ───────────── 子列表 ───────────── */

/** GET /api/library/laws/{doc_version_id}/chapters */
export function listLibraryChapters(
  docVersionId: string,
  q: LibraryPartsQuery = {},
  signal?: AbortSignal
): Promise<LibraryChapterParts> {
  const id = requireId(docVersionId, 'doc_version_id')
  return request<LibraryChapterParts>(
    `/api/library/laws/${encodeURIComponent(id)}/chapters`,
    withParams(partsParams(q), signal)
  )
}

/** GET /api/library/laws/{doc_version_id}/articles */
export function listLibraryArticles(
  docVersionId: string,
  q: LibraryPartsQuery = {},
  signal?: AbortSignal
): Promise<LibraryArticleParts> {
  const id = requireId(docVersionId, 'doc_version_id')
  return request<LibraryArticleParts>(
    `/api/library/laws/${encodeURIComponent(id)}/articles`,
    withParams(partsParams(q), signal)
  )
}

/** GET /api/library/laws/{doc_version_id}/articles/{article_id}（条款正文） */
export function getLibraryArticle(
  docVersionId: string,
  articleId: string,
  q: LibraryDetailQuery = {},
  signal?: AbortSignal
): Promise<LibraryDetail> {
  const id = requireId(docVersionId, 'doc_version_id')
  const article = requireId(articleId, 'article_id')
  return request<LibraryDetail>(
    `/api/library/laws/${encodeURIComponent(id)}/articles/${encodeURIComponent(article)}`,
    withParams(detailParams(q), signal)
  )
}

/** GET /api/library/cases/{doc_version_id}/references（处罚依据引用） */
export function listLibraryReferences(
  docVersionId: string,
  q: LibraryPartsQuery = {},
  signal?: AbortSignal
): Promise<LibraryReferenceParts> {
  const id = requireId(docVersionId, 'doc_version_id')
  return request<LibraryReferenceParts>(
    `/api/library/cases/${encodeURIComponent(id)}/references`,
    withParams(partsParams(q), signal)
  )
}
