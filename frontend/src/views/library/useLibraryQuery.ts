import { computed, onScopeDispose, ref, type ComputedRef, type Ref } from 'vue'
import { hasToken } from '@/api/client'
import { toApiError } from '@/api/errors'
import { contractState, hasRuntimeMethod, probeContract } from '@/api/dataSource'
import { LIB_COPY } from './copy'
import type { LoadState } from '@/api/types'

/**
 * 页面局部查询状态机（v0.2.3 draft-5 法规库 / 处罚案例库专用）。
 *
 * 为什么不复用全局 useAsyncData / LoadState：
 *  - 全局层把 404 的 kind 映射成 outdated，AsyncPanel 会显示与后端「范围外 / 不存在统一 404」
 *    语义冲突的契约路由文案；本模块自定义状态联合类型，按 status + code 精确映射，
 *    绝不用 e.kind === 'outdated' 判定契约状态。
 *  - 门控先行：hasToken → probeContract → hasRuntimeMethod(GET, path) 全通过才发请求；
 *    「契约 / 路由未加载」只由这一步判定，绝不从响应 404 反推。
 *  - 两层渲染：L1 页面级状态区承载 gating-* / 全部错误态 / unpublished；L2 AsyncPanel
 *    只接收 loading | empty | ready 三态（见 displayState）。
 *  - 每级详情使用独立实例 + 独立方法级门控；404 只清空当前层级 data，保留上一级与列表。
 *
 * 本文件放在 src/views/library/ 下，不进全局 src/composables/，不影响既有 9 页。
 */

export type LibraryQueryState =
  | 'gating-no-token'
  | 'gating-contract'
  | 'gating-route'
  | 'loading'
  | 'canceled'
  | 'unpublished'
  | 'empty'
  | 'ready'
  | 'auth-401'
  | 'not-found-404'
  | 'invalid-422'
  | 'schema-503'
  | 'unavailable'

/** 只有这三态允许传入 L2 AsyncPanel */
export const L2_STATES: readonly LibraryQueryState[] = ['loading', 'empty', 'ready'] as const

/** status + code 精确映射，绕开 e.kind 的 not-found / outdated 二分 */
function mapError(status: number, code: string): { state: LibraryQueryState; hint: string } {
  if (status === 404) return { state: 'not-found-404', hint: LIB_COPY.notFound404 }
  if (status === 401 || status === 403) return { state: 'auth-401', hint: LIB_COPY.auth401 }
  if (status === 422) {
    return {
      state: 'invalid-422',
      hint: code === 'violation_filter_case_only' ? LIB_COPY.invalid422Violation : LIB_COPY.invalid422
    }
  }
  if (status === 503 && code === 'library_schema_not_installed') {
    return { state: 'schema-503', hint: LIB_COPY.schema503 }
  }
  // 其余 5xx / 0 / 其它 4xx 一律 unavailable，不落到 error / outdated
  return { state: 'unavailable', hint: LIB_COPY.unavailable }
}

function defaultEmpty(value: unknown): boolean {
  if (value == null) return true
  if (Array.isArray(value)) return value.length === 0
  if (typeof value === 'object') {
    const list = (value as Record<string, unknown>).list
    if (Array.isArray(list)) return list.length === 0
  }
  return false
}

function isUnpublished(value: unknown): boolean {
  return !!value && typeof value === 'object' &&
    (value as Record<string, unknown>).status === 'unpublished'
}

export interface UseLibraryQueryOptions<T> {
  /** 运行期方法级门控路径（OpenAPI 模板）；用 getter 支持动态子路由 */
  path: () => string
  fetcher: (signal: AbortSignal) => Promise<T>
  /** 列表查询：status=unpublished 识别为合法空态 */
  detectUnpublished?: boolean
  /** 成功后的空判定；默认按 data.list 长度 */
  isEmpty?: (data: T) => boolean
}

export interface LibraryQueryResult<T> {
  state: Ref<LibraryQueryState>
  data: Ref<T | null>
  /** L1 统一文案（不是统一错误层的 hint 原文） */
  hint: Ref<string>
  started: Ref<boolean>
  loading: ComputedRef<boolean>
  isL2: ComputedRef<boolean>
  /** 仅 loading | empty | ready；no-permission / outdated / unavailable / error 一律不传入 */
  displayState: ComputedRef<LoadState>
  run: () => Promise<void>
  cancel: () => void
  /** 清空当前层级 data 与状态；保留筛选快照与上一级 */
  clear: () => void
}

/** LibraryStatePanel 只需要这些字段；用结构类型避免泛型 Ref 的方差问题 */
export interface LibraryQueryView {
  state: { value: LibraryQueryState }
  hint: { value: string }
  started: { value: boolean }
  isL2: { value: boolean }
  displayState: { value: LoadState }
  run: () => Promise<void>
  clear: () => void
}

export function useLibraryQuery<T>(options: UseLibraryQueryOptions<T>): LibraryQueryResult<T> {
  const state = ref<LibraryQueryState>('gating-contract') as Ref<LibraryQueryState>
  const data = ref<T | null>(null) as Ref<T | null>
  const hint = ref('')
  const started = ref(false)
  const loading = computed(() => state.value === 'loading')
  const isL2 = computed(() => L2_STATES.includes(state.value))
  const displayState = computed<LoadState>(() => {
    if (state.value === 'loading') return 'loading'
    if (state.value === 'ready') return 'ready'
    // 只有 loading | empty | ready 会走 L2；其它态由 L1 承载，这里给 empty 占位
    return 'empty'
  })

  let controller: AbortController | null = null

  function cancel() {
    if (controller) {
      controller.abort()
      controller = null
    }
  }

  function clear() {
    cancel()
    data.value = null
    hint.value = ''
    started.value = false
    state.value = 'gating-contract'
  }

  async function run(): Promise<void> {
    cancel()
    data.value = null
    hint.value = ''
    started.value = true
    const targetPath = options.path()

    // 1) 凭证
    if (!hasToken()) {
      state.value = 'gating-no-token'
      hint.value = LIB_COPY.noToken
      return
    }
    // 2) 运行期契约（门控先行；契约 / 路由未加载只在这里判定，绝不由响应 404 反推）
    if (contractState.value !== 'ready') await probeContract()
    if (contractState.value !== 'ready') {
      state.value = 'gating-contract'
      hint.value = LIB_COPY.contract
      return
    }
    // 3) 方法级门控
    if (!hasRuntimeMethod('GET', targetPath)) {
      state.value = 'gating-route'
      hint.value = LIB_COPY.gate(targetPath)
      return
    }
    // 4) 发请求
    state.value = 'loading'
    const ctrl = new AbortController()
    controller = ctrl
    try {
      const result = await options.fetcher(ctrl.signal)
      if (ctrl.signal.aborted) return
      data.value = result
      if (options.detectUnpublished && isUnpublished(result)) {
        state.value = 'unpublished'
        hint.value = LIB_COPY.unpublished
        return
      }
      const empty = options.isEmpty ? options.isEmpty(result) : defaultEmpty(result)
      state.value = empty ? 'empty' : 'ready'
      hint.value = empty ? LIB_COPY.empty : ''
    } catch (err) {
      if (ctrl.signal.aborted) return
      const e = toApiError(err)
      if (e.kind === 'canceled') {
        state.value = 'canceled'
        hint.value = LIB_COPY.canceled
        data.value = null
        return
      }
      const mapped = mapError(e.status, e.code)
      state.value = mapped.state
      hint.value = mapped.hint
      data.value = null // 只清空当前层级，保留上一级与列表
    } finally {
      if (controller === ctrl) controller = null
    }
  }

  onScopeDispose(cancel)

  return { state, data, hint, started, loading, isL2, displayState, run, cancel, clear }
}
