<template>
  <div class="lib-state" data-lib-section="state">
    <!-- 尚未发起该层级查询：中性占位，不显示数据、不显示错误 -->
    <div v-if="!query.started.value" class="mr-disabled-hint">{{ neutralText }}</div>

    <!-- L1：门控态 / 全部错误态 / 合法空态 / 请求取消，一律不经过 AsyncPanel -->
    <div v-else-if="!query.isL2.value" class="lib-l1" data-lib-layer="l1" role="group">
      <template v-if="isGating">
        <div class="lib-l1-head">
          <el-tag type="warning" effect="plain">{{ gatingTag }}</el-tag>
          <span class="lib-l1-title">{{ gatingTitle }}</span>
        </div>
        <p class="lib-lead">{{ query.hint.value }}</p>
        <div class="mr-disabled-hint">{{ LIB_COPY.stateNote }}</div>
        <div class="lib-l1-actions">
          <el-button size="small" @click="retry">重新检查</el-button>
        </div>
      </template>

      <el-alert v-else-if="isError" type="error" :closable="false" show-icon role="alert"
        :title="errorTitle" :description="query.hint.value">
        <template #default>
          <div class="lib-l1-actions">
            <el-button size="small" @click="retry">重试查询</el-button>
            <el-button v-if="showBackParent" size="small" @click="emit('back-parent')">返回上一级</el-button>
            <el-button v-if="showBackList" size="small" @click="emit('back-list')">返回列表</el-button>
          </div>
        </template>
      </el-alert>

      <el-alert v-else-if="query.state.value === 'unpublished'" type="info" :closable="false"
        title="合法空态：status=unpublished" :description="query.hint.value">
        <el-button size="small" @click="retry">重新查询</el-button>
      </el-alert>

      <el-alert v-else type="info" :closable="false" title="请求已取消" :description="query.hint.value">
        <el-button size="small" @click="retry">重新查询</el-button>
      </el-alert>
    </div>

    <!-- L2：AsyncPanel 只接 loading | empty | ready 三态 -->
    <div v-else data-lib-layer="l2">
      <div v-if="query.displayState.value === 'loading'" class="lib-live" aria-live="polite" aria-atomic="true">
        正在从后端加载真实数据…
      </div>
      <AsyncPanel :state="query.displayState.value" error="" loading-text="正在从后端加载真实数据…" @retry="retry">
        <template #empty>
          <el-empty :image-size="70" :description="emptyText || query.hint.value">
            <el-button size="small" @click="retry">重新查询</el-button>
          </el-empty>
        </template>
        <slot />
      </AsyncPanel>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import AsyncPanel from '@/components/AsyncPanel.vue'
import { LIB_COPY } from './copy'
import type { LibraryQueryState, LibraryQueryView } from './useLibraryQuery'

/**
 * draft-5 两页专用 L1 / L2 两层渲染。
 * L1 自管门控态、全部错误态与 unpublished；L2 AsyncPanel 只接 loading | empty | ready，
 * 因此 AsyncPanel 的 no-permission / outdated / unavailable / error 四个分支永远不会被渲染，
 * 从根上杜绝与契约语义冲突的全局文案出现在这两页。
 */
const props = withDefaults(
  defineProps<{
    query: LibraryQueryView
    emptyText?: string
    showBackParent?: boolean
    showBackList?: boolean
    neutralText?: string
  }>(),
  {
    emptyText: '',
    showBackParent: false,
    showBackList: true,
    neutralText: '尚未发起该层级查询。'
  }
)

const emit = defineEmits<{
  (e: 'retry'): void
  (e: 'back-parent'): void
  (e: 'back-list'): void
}>()

function retry() {
  emit('retry')
}

const isGating = computed(() => props.query.state.value.startsWith('gating-'))
const ERROR_STATES: LibraryQueryState[] = [
  'auth-401', 'not-found-404', 'invalid-422', 'schema-503', 'unavailable'
]
const isError = computed(() => ERROR_STATES.includes(props.query.state.value))

const GATING_TAGS: Record<string, string> = {
  'gating-no-token': '未配置凭证',
  'gating-contract': '契约未就绪',
  'gating-route': '接口未加载'
}
const GATING_TITLES: Record<string, string> = {
  'gating-no-token': '未配置会话凭证',
  'gating-contract': '运行期契约未就绪',
  'gating-route': '运行期未加载该接口'
}
const ERROR_TITLES: Record<string, string> = {
  'auth-401': '未认证 / 无权限（401 / 403）',
  'not-found-404': '未找到对象（404）',
  'invalid-422': '参数不被接受（422）',
  'schema-503': '新库 Schema 未安装（503）',
  unavailable: '服务暂不可用'
}

const gatingTag = computed(() => GATING_TAGS[props.query.state.value] || '入口已禁用')
const gatingTitle = computed(() => GATING_TITLES[props.query.state.value] || '入口已禁用')
const errorTitle = computed(() => ERROR_TITLES[props.query.state.value] || '请求失败')
</script>
