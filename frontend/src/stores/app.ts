import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { getToken, setToken, clearToken } from '@/api/client'
import { getParseInfo } from '@/api/parse'
import { releaseStatus } from '@/config/release'
import type { ComponentState, ParseServiceInfo } from '@/api/types'

export const useAppStore = defineStore('app', () => {
  const token = ref(getToken())
  const apiOnline = ref<'unknown' | 'online' | 'offline'>('unknown')
  const serviceInfo = ref<ParseServiceInfo | null>(null)
  /**
   * 后端 MVP 有限范围 QA 结论（2026-11-11 PASS）。
   * 裁决明确不含「独立前端全部联调」，因此前端整体不可用此值宣称正式可用；
   * 保留该字段仅作状态追踪，页面文案统一取自 config/release.ts。
   */
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
    await probeBackend()
  }

  function logout() {
    clearToken()
    token.value = ''
    apiOnline.value = 'unknown'
    serviceInfo.value = null
  }

  /** 唯一真实的后端探活：GET /api/parse/info */
  async function probeBackend() {
    try {
      serviceInfo.value = await getParseInfo()
      apiOnline.value = 'online'
    } catch {
      apiOnline.value = 'offline'
      serviceInfo.value = null
    }
  }

  return {
    token, apiOnline, apiState, serviceInfo, qaAccepted,
    saveToken, logout, probeBackend
  }
})
