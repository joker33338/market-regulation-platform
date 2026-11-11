<template>
  <AsyncPanel :state="state" :error="error" @retry="emit('retry')">
    <template #empty>
      <slot name="empty"><el-empty :image-size="70" description="暂无符合条件的数据" /></slot>
    </template>

    <!-- 搜索区由 columns[].search 自动生成（借鉴 Geeker Admin ProTable「列配置即契约」） -->
    <div v-if="searchColumns.length" class="mr-pro-search">
      <template v-for="col in searchColumns" :key="col.prop">
        <el-input
          v-if="col.search?.el === 'input'"
          v-model="searchModel[col.prop]"
          :placeholder="col.search.placeholder || `搜索${col.label}`"
          clearable
          style="width: 220px"
          @keyup.enter="search"
        />
        <el-select
          v-else-if="col.search?.el === 'select'"
          v-model="searchModel[col.prop]"
          :placeholder="col.search.placeholder || col.label"
          clearable
          style="width: 150px"
          @change="search"
        >
          <el-option
            v-for="o in col.search.options || []"
            :key="String(o.value)"
            :label="o.label"
            :value="o.value"
          />
        </el-select>
        <el-date-picker
          v-else-if="col.search?.el === 'dateRange'"
          v-model="searchModel[col.prop]"
          type="daterange"
          value-format="YYYY-MM-DD"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          style="width: 250px"
          @change="search"
        />
      </template>
      <el-button type="primary" @click="search">查询</el-button>
      <el-button @click="reset">重置</el-button>
      <el-button @click="emitQuery">刷新</el-button>
      <div v-if="$slots.toolbar" class="mr-pro-tools"><slot name="toolbar" /></div>
    </div>

    <el-table
      :data="rows"
      v-loading="loading"
      style="margin-top: 12px; width: 100%"
      @sort-change="onSortChange"
    >
      <el-table-column
        v-for="col in columns"
        :key="col.prop"
        :prop="col.prop"
        :label="col.label"
        :width="col.width"
        :min-width="col.minWidth"
        :sortable="col.sortable ? 'custom' : false"
        :fixed="col.fixed"
        :align="col.align"
        :show-overflow-tooltip="col.showOverflowTooltip"
      >
        <template #default="scope">
          <slot :name="`col-${col.prop}`" :row="scope.row" :value="scope.row[col.prop]">
            {{ scope.row[col.prop] ?? '—' }}
          </slot>
        </template>
      </el-table-column>
      <slot name="extra-columns" />
      <template #empty><span class="mr-pro-empty">暂无符合条件的数据</span></template>
    </el-table>

    <div class="mr-pro-pager">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSizeModel"
        :total="total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next, jumper"
        background
        @current-change="emitQuery"
        @size-change="onSizeChange"
      />
    </div>
  </AsyncPanel>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import AsyncPanel from './AsyncPanel.vue'
import type { LoadState } from '@/api/types'

/**
 * 轻量 MrProTable（v0.2.2 受控模式）
 * 借鉴 Geeker Admin ProTable 的 columns→搜索表单契约，但数据获取完全交给页面 useAsyncData：
 *   emit('query', {page,pageSize,search,sortBy,order}) → 页面调用真实 API → 回传 rows/total/state
 * Loading / Empty / Error / Retry / NoPermission / ServiceUnavailable 六态由 AsyncPanel 统一呈现；
 * 组件内部不吞错误、不回退 DEMO、不自行发起请求。
 */
interface SearchOption { label: string; value: string | number }
interface ColumnSearch {
  el: 'input' | 'select' | 'dateRange'
  placeholder?: string
  options?: SearchOption[]
  defaultValue?: unknown
}
export interface MrColumn {
  prop: string
  label: string
  width?: number | string
  minWidth?: number | string
  sortable?: boolean
  fixed?: boolean | string
  align?: 'left' | 'center' | 'right'
  showOverflowTooltip?: boolean
  search?: ColumnSearch
}
export interface MrQuery {
  page: number
  pageSize: number
  search: Record<string, unknown>
  sortBy: string
  order: string
}

const props = withDefaults(
  defineProps<{
    columns: MrColumn[]
    rows: Record<string, unknown>[]
    total: number
    loading?: boolean
    state?: LoadState
    error?: string
    pageSize?: number
  }>(),
  { loading: false, state: 'ready', error: '', pageSize: 20 }
)

const emit = defineEmits<{
  (e: 'query', payload: MrQuery): void
  (e: 'retry'): void
}>()

const page = ref(1)
const pageSizeModel = ref(props.pageSize)
const sortBy = ref('')
const order = ref('')
const searchModel = reactive<Record<string, unknown>>({})
const searchColumns = computed(() => props.columns.filter((c) => !!c.search))

function initModel() {
  for (const c of props.columns) {
    if (c.search) searchModel[c.prop] = c.search.defaultValue ?? (c.search.el === 'dateRange' ? null : '')
  }
}
initModel()

function emitQuery() {
  emit('query', {
    page: page.value,
    pageSize: pageSizeModel.value,
    search: { ...searchModel },
    sortBy: sortBy.value,
    order: order.value
  })
}

function search() {
  page.value = 1
  emitQuery()
}

function reset() {
  initModel()
  sortBy.value = ''
  order.value = ''
  search()
}

function onSizeChange() {
  page.value = 1
  emitQuery()
}

function onSortChange(payload: { prop?: string; order?: string | null }) {
  sortBy.value = payload.prop || ''
  order.value = payload.order === 'ascending' ? 'asc' : payload.order === 'descending' ? 'desc' : ''
  emitQuery()
}

function refresh() {
  emitQuery()
}

defineExpose({ refresh, search, reset })

onMounted(emitQuery)
</script>
