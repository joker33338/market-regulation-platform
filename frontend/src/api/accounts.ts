import client from './client'
import type {
  AccountCreate, AccountEventPage, AccountPage, AccountUpdate, AccountView,
  LoginRequest, LoginResponse, LogoutResponse, RoleCatalog
} from './types'

/**
 * v0.2.3 draft-4 账号密码与会话接口（契约源：frontend-openapi-v023-draft4.json）
 *
 * 口径（backend handoff e24cbad）：
 *  - POST /api/auth/login 匿名可调用：username + password → 短期 Bearer（expires_in=3600）+ Principal；
 *    用户名不存在与密码错误统一 401 invalid_credentials（不提示账号枚举）；限流 429。
 *  - POST /api/auth/logout 需 Bearer：仅新会话支持服务端撤销；旧独立 Token 返回 409，
 *    前端只能清除本机会话，不得宣称服务端已撤销旧凭证。
 *  - 账号管理五接口均需 ADMIN（hasRuntimeMethod 门控 + 后端逐请求校验）；
 *    密码不存浏览器、不入日志；后端不回显密码或哈希。
 *  - 用户名 3–64 位 [A-Za-z0-9_.@-]、首位字母/数字、大小写不敏感；密码 12–256 字符。
 *
 * 运行期是否可用：8180 正式实例仍为 v0.2.2（无这些路由），调用方必须先经
 * hasRuntimeMethod('POST', '/api/auth/login') 等门控，失败按真实错误态呈现。
 */

function signalOf(signal?: AbortSignal) {
  return signal ? { signal } : {}
}

/** POST /api/auth/login —— 匿名；成功后由调用方保存 access_token 并重新 GET /api/auth/me */
export function login(body: LoginRequest, signal?: AbortSignal): Promise<LoginResponse> {
  return client
    .post<LoginResponse>('/api/auth/login', body, signalOf(signal))
    .then((r) => r.data)
}

/** POST /api/auth/logout —— 撤销当前会话；旧独立 Token 会 409，调用方如实提示 */
export function logout(signal?: AbortSignal): Promise<LogoutResponse> {
  return client
    .post<LogoutResponse>('/api/auth/logout', undefined, signalOf(signal))
    .then((r) => r.data)
}

/** GET /api/auth/roles —— 三类角色定义、all_permissions 口径与安全门禁 */
export function getRoles(signal?: AbortSignal): Promise<RoleCatalog> {
  return client.get<RoleCatalog>('/api/auth/roles', signalOf(signal)).then((r) => r.data)
}

/** GET /api/admin/accounts —— 真实账号分页（无密码 / 哈希字段） */
export function listAccounts(
  q: { page: number; pageSize: number },
  signal?: AbortSignal
): Promise<AccountPage> {
  return client
    .get<AccountPage>('/api/admin/accounts', {
      params: { page: q.page, page_size: q.pageSize },
      ...signalOf(signal)
    })
    .then((r) => r.data)
}

/** POST /api/admin/accounts —— 创建账号（服务端生成 principal_id / owner） */
export function createAccount(body: AccountCreate, signal?: AbortSignal): Promise<AccountView> {
  return client
    .post<AccountView>('/api/admin/accounts', body, signalOf(signal))
    .then((r) => r.data)
}

/** PATCH /api/admin/accounts/{principal_id} —— 改角色 / 范围 / 状态 / 重置密码 */
export function patchAccount(
  principalId: string,
  body: AccountUpdate,
  signal?: AbortSignal
): Promise<AccountView> {
  return client
    .patch<AccountView>(`/api/admin/accounts/${encodeURIComponent(principalId)}`, body, signalOf(signal))
    .then((r) => r.data)
}

/** GET /api/admin/account-events —— 账号变更审计（含 before/after，不含密码） */
export function listAccountEvents(
  q: { page: number; pageSize: number },
  signal?: AbortSignal
): Promise<AccountEventPage> {
  return client
    .get<AccountEventPage>('/api/admin/account-events', {
      params: { page: q.page, page_size: q.pageSize },
      ...signalOf(signal)
    })
    .then((r) => r.data)
}
