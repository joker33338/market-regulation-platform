import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { getToken, setToken, clearToken } from '@/api/client'
import { getParseInfo } from '@/api/parse'
import { login as apiLogin, logout as apiLogout } from '@/api/accounts'
import { hasServerLogout } from '@/api/dataSource'
import { probeContract, resetContractState } from '@/api/dataSource'
import { loadPrincipal, clearPrincipal } from '@/api/principal'
import { releaseStatus } from '@/config/release'
import { toApiError } from '@/api/errors'
import type { ComponentState, ParseServiceInfo } from '@/api/types'

/**
 * 会话状态（v0.2.3 draft-4 起支持两种凭证来源）：
 *  - token：既有 PARSING_API_TOKENS_JSON 独立 Token（8180 v0.2.2 唯一可用模式）；
 *  - password：账号密码登录签发的短期 Bearer（POST /api/auth/login，expires_in=3600）。
 * authMode 只决定登出时是否尝试服务端撤销（POST /api/auth/logout 仅新会话支持，
 * 旧独立 Token 返回 409 —— 前端只清本机会话，不宣称服务端已撤销）。
 */
const AUTH_MODE_KEY = 'mrp_auth_mode'

function readAuthMode(): 'token' | 'password' {
  try {
    return sessionStorage.getItem(AUTH_MODE_KEY) === 'password' ? 'password' : 'token'
  } catch {
    return 'token'
  }
}

function writeAuthMode(value: 'token' | 'password') {
  try {
    sessionStorage.setItem(AUTH_MODE_KEY, value)
  } catch {
    /* 隐私模式仅保留内存态 */
  }
}

export const useAppStore = defineStore('app', () => {
  const token = ref(getToken())
  const authMode = ref<'token' | 'password'>(readAuthMode())
  const apiOnline = ref<'unknown' | 'online' | 'offline'>('unknown')
  const serviceInfo = ref<ParseServiceInfo | null>(null)
  /** v0.2.1 后端 MVP 有限范围 QA PASS；不代表 v0.2.2/v0.2.3 前端已联调或生产可用 */
  const qaAccepted = ref(releaseStatus.backendQa === 'PASS')

  /** 组件五态：只有真实探活成功才允许 ONLINE；未探测一律 UNKNOWN */
  const apiState = computed<ComponentState>(() => {
    if (apiOnline.value === 'online') return 'ONLINE'
    if (apiOnline.value === 'offline') return 'OFFLINE'
    return 'UNKNOWN'
  })

  async function saveToken(value: string) {
    setToken(value)
    token.value = value
    authMode.value = 'token'
    writeAuthMode('token')
    await probeAll()
  }

  /**
   * 账号密码登录（draft-4）：密码只在内存中短暂停留，随请求体发送后立即清空；
   * 成功后保存返回的短期 Bearer，再重新确认身份与运行期契约。
   */
  async function passwordLogin(username: string, password: string): Promise<string | null> {
    const res = await apiLogin({ username, password })
    if (!res.access_token) throw new Error('登录响应缺少 access_token')
    setToken(res.access_token)
    token.value = res.access_token
    authMode.value = 'password'
    writeAuthMode('password')
    await probeAll()
    return res.principal?.principal_id || null
  }

  /**
   * 登出：账号会话先尝试服务端撤销（仅新会话支持，旧 Token 409）；
   * 无论撤销结果如何都清除本机会话与身份缓存，不把网络失败伪装成已撤销。
   */
  async function logout() {
    let revoked = false
    if (authMode.value === 'password' && hasServerLogout()) {
      try {
        const res = await apiLogout()
        revoked = res.revoked === true
      } catch (err) {
        const e = toApiError(err)
        revoked = false
        void e // 409/网络失败：仅清本机会话，不宣称服务端已撤销
      }
    }
    clearToken()
    token.value = ''
    authMode.value = 'token'
    writeAuthMode('token')
    apiOnline.value = 'unknown'
    serviceInfo.value = null
    clearPrincipal('已清除会话凭证')
    resetContractState()
    return revoked
  }

  /** 旧解析接口唯一真实探活：GET /api/parse/info */
  async function probeBackend() {
    try {
      serviceInfo.value = await getParseInfo()
      apiOnline.value = 'online'
    } catch {
      apiOnline.value = 'offline'
      serviceInfo.value = null
    }
  }

  /** 探测旧服务探活、运行期契约与当前登录人员；身份最后确认，401/403 广播可清掉旧契约缓存 */
  async function probeAll() {
    await Promise.all([probeBackend(), probeContract(true)])
    await loadPrincipal(true)
  }

  return {
    token, authMode, apiOnline, apiState, serviceInfo, qaAccepted,
    saveToken, passwordLogin, logout, probeBackend, probeAll
  }
})
