import { computed, ref } from 'vue'
import client from './client'
import { hasToken } from './client'
import { toApiError } from './errors'
import { onAuthStateChange } from './authEvents'
import { contractState, resetContractState } from './dataSource'
import type { PrincipalInfo, ReviewIdentityFields } from './types'

/**
 * v0.2.3 draft-4 身份层 —— GET /api/auth/me 是全站唯一的「当前登录人员」事实来源。
 *
 * 硬边界：
 *  - principal_id（实际操作者）与 owner_id（业务数据归属）分离，不能互相推导；
 *  - roles / permissions / data_scope 只用于**展示与收紧**，绝不用于放宽写授权；
 *    审核写按钮仍以运行期契约 + 详情 review_write_supported / review_ledger.available 双门控为准，
 *    最终授权由后端按每次请求的 Principal 与目标文档 owner 判定；
 *  - draft-4 起 ADMIN 拥有全部业务权限（all_permissions，覆盖 draft-2「ADMIN 不隐含 REVIEWER」
 *    旧口径）；USER 仍不具备审核写入能力；
 *  - 401/403 立即清除身份与运行期契约缓存，避免凭证失效/角色撤销后残留旧可写状态；
 *    404（范围撤销或对象越界）触发身份重新确认；
 *  - 本模块不读取、不保存、不输出任何凭证或私密 runtime 配置。
 */
export type PrincipalState = 'unknown' | 'ready' | 'no-permission' | 'unavailable' | 'error'

export const principal = ref<PrincipalInfo | null>(null)
export const principalState = ref<PrincipalState>('unknown')
export const principalError = ref('')
export const principalLoadedAt = ref('')
/** 404 只做标记，由页面/提交前显式重新确认；避免在 404 回调里再次请求形成循环 */
export const principalNeedsRefresh = ref(false)

let inflight: Promise<PrincipalInfo | null> | null = null

export function clearPrincipal(reason = '') {
  principal.value = null
  principalState.value = 'unknown'
  principalError.value = reason
  principalLoadedAt.value = ''
  principalNeedsRefresh.value = false
}

/** 每次调用都向后端重新确认身份；不使用本地缓存的旧身份做授权展示 */
export async function loadPrincipal(force = false): Promise<PrincipalInfo | null> {
  if (!force && inflight) return inflight
  if (!hasToken()) {
    clearPrincipal('未配置 API Token：请在系统监控页配置会话凭证后再确认身份')
    return null
  }
  inflight = (async () => {
    try {
      const res = await client.get<PrincipalInfo>('/api/auth/me')
      const p = res.data
      // 契约五个字段全部必填；缺字段不臆造、不降级放行
      if (
        !p || typeof p.principal_id !== 'string' ||
        !Array.isArray(p.roles) || !Array.isArray(p.review_owner_scopes) ||
        !('owner_id' in p) || !('credential_status' in p)
      ) {
        throw new Error('GET /api/auth/me 响应缺少必填身份字段')
      }
      principal.value = p
      principalLoadedAt.value = new Date().toISOString()
      principalNeedsRefresh.value = false
      principalError.value = ''
      principalState.value = p.credential_status === 'active' ? 'ready' : 'no-permission'
      if (p.credential_status !== 'active') {
        principalError.value = `凭证状态为 ${p.credential_status}，后端将拒绝后续请求`
      }
      return p
    } catch (err) {
      const e = toApiError(err)
      principal.value = null
      principalState.value =
        e.status === 401 || e.status === 403 ? 'no-permission'
          : e.status === 0 || e.status >= 500 ? 'unavailable' : 'error'
      principalError.value = e.hint
      principalLoadedAt.value = ''
      return null
    }
  })().finally(() => {
    inflight = null
  })
  return inflight
}

/** 仅展示：当前身份是否显式具备 REVIEWER 角色（有角色也不代表已获写授权） */
export const isReviewerIdentity = computed(() =>
  principalState.value === 'ready' && !!principal.value?.roles.includes('REVIEWER')
)

/** 仅展示：当前身份是否具备 ADMIN 角色；draft-4 起 ADMIN 拥有全部业务权限 */
export const isAdminIdentity = computed(() =>
  principalState.value === 'ready' && !!principal.value?.roles.includes('ADMIN')
)

/** 服务端权限口径（draft-4 /auth/me 提供）；缺失时为空，不推断 */
export const principalPermissions = computed(() =>
  principalState.value === 'ready' ? (principal.value?.permissions || []) : []
)

/**
 * 只用于**收紧**：明确已确认身份且既无 REVIEWER 也无 ADMIN 时，页面不得展示可用审核写入能力。
 * draft-4 起 ADMIN 全权限（all_permissions），仅含 ADMIN 也可写；身份未加载 / 加载失败时返回
 * false，由原双门控继续决定，绝不因未知身份而放宽。
 */
export const identityBlocksWrite = computed(() =>
  principalState.value === 'ready' && !!principal.value &&
  !principal.value.roles.includes('REVIEWER') &&
  !principal.value.roles.includes('ADMIN')
)

export const principalRoleText = computed(() => {
  const p = principal.value
  if (principalState.value !== 'ready' || !p) return '未确认'
  return p.roles.length ? p.roles.join('、') : '无角色'
})

export const principalScopeText = computed(() => {
  const p = principal.value
  if (principalState.value !== 'ready' || !p) return '未确认'
  return p.review_owner_scopes.length ? p.review_owner_scopes.join('、') : '无（空范围不产生审核授权）'
})

export const principalOwnerText = computed(() => {
  const p = principal.value
  if (principalState.value !== 'ready' || !p) return '未确认'
  return p.owner_id || '无个人 owner（纯审核身份）'
})

/** 事件/回执身份展示：旧事件字段为 null 时如实显示未知，不把历史 owner 补认成具体人员 */
export function identityText(value: string | null | undefined): string {
  return typeof value === 'string' && value.length > 0 ? value : '未知（历史记录）'
}

export function identityModelText(fields: ReviewIdentityFields): string {
  if (fields.identity_model === 'principal-v1') return 'principal-v1'
  if (fields.identity_model === 'legacy-owner') return 'legacy-owner（历史 owner 别名，非具体人员）'
  return fields.identity_model || '未标注（按历史记录处理）'
}

/* 401/403：凭证失效或角色/范围被撤销，立即清除身份与运行期契约缓存，
   让双门控失效，避免页面继续展示旧的可写状态。
   404：目标对象不在当前授权范围（或该服务未提供 draft-2 身份接口）——只标记需重新确认，
   由页面在提交前显式 loadPrincipal(true)，不在此处发请求以避免 404 递归。 */
onAuthStateChange((status) => {
  if (status === 401 || status === 403) {
    clearPrincipal(status === 401
      ? '凭证失效或未认证（401）：已清除身份与运行期契约缓存，请重新配置有效凭证'
      : '无权访问（403）：当前身份无该操作权限或目标不在授权范围，已清除旧身份与契约缓存')
    resetContractState()
    // 保留明确的未认证/无权限态，避免 AsyncPanel 把撤销误显示为「探测失败」
    contractState.value = 'no-permission'
  } else if (status === 404) {
    principalNeedsRefresh.value = true
  }
})
