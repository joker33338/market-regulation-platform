import { computed, onScopeDispose, ref, type Ref } from 'vue'
import { hasToken } from '@/api/client'
import { toApiError } from '@/api/errors'
import { contractState, probeContract, type ContractState } from '@/api/dataSource'
import type { LoadState } from '@/api/types'

/**
 * 七页面统一异步状态：Loading / Empty / Error / Retry / No Permission / Service Unavailable / Outdated
 *
 * 设计要点（对应任务第十阶段）：
 *  - 查询前先做运行期契约探测；未就绪不发起业务请求，直接呈现真实异常态，绝不回退 DEMO
 *  - 每次 load 取消上一次请求（页面切换 / 快速筛选不产生重复请求）
 *  - 组件作用域销毁时自动 abort，避免页面卸载后仍写入状态或无限加载
 *  - 空数组 / null / 空列表统一识别为 Empty
 *  - 错误经 ApiError 归一化，不把后端原文或凭证透出
 */
export interface AsyncData<T> {
  data: Ref<T | null>
  state: Ref<LoadState>
  error: Ref<string>
  loading: Readonly<Ref<boolean>>
  load: () => Promise<void>
  cancel: () => void
}

export interface AsyncDataOptions<T> {
  /** 默认 true：挂载即加载 */
  immediate?: boolean
  /** 自定义空判定 */
  isEmpty?: (data: T) => boolean
  /** 默认 true：要求运行期 v0.2.2 契约就绪；旧解析接口手动查询可设为 false */
  requireContract?: boolean
}

function defaultEmpty<T>(value: T): boolean {
  if (value == null) return true
  if (Array.isArray(value)) return value.length === 0
  if (typeof value === 'object') {
    const list = (value as Record<string, unknown>).list
    if (Array.isArray(list)) return list.length === 0
  }
  return false
}

function contractToState(value: ContractState): LoadState | null {
  switch (value) {
    case 'ready': return null
    case 'no-permission': return 'no-permission'
    case 'outdated': return 'outdated'
    case 'unavailable': return 'unavailable'
    case 'error': return 'error'
    default: return 'error'
  }
}

function kindToState(kind: string): LoadState {
  if (kind === 'canceled') return 'loading'
  if (kind === 'no-permission') return 'no-permission'
  if (kind === 'outdated' || kind === 'not-found') return 'outdated'
  if (kind === 'unavailable') return 'unavailable'
  return 'error'
}

export function useAsyncData<T>(
  fetcher: (signal: AbortSignal) => Promise<T>,
  options: AsyncDataOptions<T> = {}
): AsyncData<T> {
  const { immediate = true, requireContract = true } = options
  const data = ref<T | null>(null) as Ref<T | null>
  const state = ref<LoadState>('loading') as Ref<LoadState>
  const error = ref('')
  const loading = computed(() => state.value === 'loading')
  let controller: AbortController | null = null

  function cancel() {
    if (controller) {
      controller.abort()
      controller = null
    }
  }

  async function load(): Promise<void> {
    cancel()
    error.value = ''
    state.value = 'loading'

    if (!hasToken()) {
      state.value = 'no-permission'
      error.value = '未配置 API Token，请在系统监控页配置有效会话凭证后再查询'
      return
    }

    if (requireContract) {
      const current = contractState.value === 'ready' ? 'ready' : await probeContract()
      const blocked = contractToState(current)
      if (blocked) {
        state.value = blocked
        error.value = contractState.value === 'unknown' ? '运行期接口探测失败，请重试' : ''
        return
      }
    }

    const ctrl = new AbortController()
    controller = ctrl
    try {
      const result = await fetcher(ctrl.signal)
      if (ctrl.signal.aborted) return
      data.value = result
      state.value = (options.isEmpty || defaultEmpty)(result) ? 'empty' : 'ready'
    } catch (err) {
      if (ctrl.signal.aborted) return
      const e = toApiError(err)
      if (e.kind === 'canceled') return
      const next = kindToState(e.kind)
      if (next === 'loading') return
      state.value = next
      error.value = e.hint
      data.value = null
    } finally {
      if (controller === ctrl) controller = null
    }
  }

  onScopeDispose(cancel)

  if (immediate) void load()
  return { data, state, error, loading, load, cancel }
}
