import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { getToken, setToken, clearToken } from '@/api/client'
import { getParseInfo } from '@/api/parse'
import { probeContract, resetContractState } from '@/api/dataSource'
import { loadPrincipal, clearPrincipal } from '@/api/principal'
import { releaseStatus } from '@/config/release'
import type { ComponentState, ParseServiceInfo } from '@/api/types'

export const useAppStore = defineStore('app', () => {
  const token = ref(getToken())
  const apiOnline = ref<'unknown' | 'online' | 'offline'>('unknown')
  const serviceInfo = ref<ParseServiceInfo | null>(null)
  /** v0.2.1 后端 MVP 有限范围 QA PASS；不代表 v0.2.2 前端已联调或生产可用 */
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
    await probeAll()
  }

  function logout() {
    clearToken()
    token.value = ''
    apiOnline.value = 'unknown'
    serviceInfo.value = null
    clearPrincipal('已清除会话凭证')
    resetContractState()
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
    token, apiOnline, apiState, serviceInfo, qaAccepted,
    saveToken, logout, probeBackend, probeAll
  }
})
