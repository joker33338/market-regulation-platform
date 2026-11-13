<template>
  <!-- 搜索区放在状态面板之外：空态 / 错误态下仍可改筛选条件，不被 AsyncPanel 整体替换 -->
  <div class="mr-pro-table">
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

    <AsyncPanel :state="state" :error="error" @retry="emit('retry')">
      <template #empty>
        <slot name="empty">
          <el-empty :image-size="70" :description="emptyText">
            <div class="mr-empty-actions">
              <el-button size="small" @click="refresh">刷新</el-button>
              <el-tooltip
                :content="hasActiveFilter
                  ? '清空当前筛选条件，返回全部数据'
                  : '当前没有生效的筛选条件，后端返回的就是全部数据，无需返回'"
                placement="top"
              >
                <span>
                  <el-button size="small" :disabled="!hasActiveFilter" @click="reset">返回</el-button>
                </span>
              </el-tooltip>
            </div>
          </el-empty>
        </slot>
      </template>

      <el-table
        ref="tableRef"
        :data="rows"
        v-loading="loading"
        style="margin-top: 12px; width: 100%"
        max-height="520"
        @sort-change="onSortChange"
        @selection-change="onSelectionChange"
      >
        <el-table-column v-if="selectable" type="selection" width="46" fixed="left" />
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
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import AsyncPanel from './AsyncPanel.vue'
import type { LoadState } from '@/api/types'

/**
 * 轻量 MrProTable（v0.2.2 受控模式）
 * 借鉴 Geeker Admin ProTable 的 columns→搜索表单契约，但数据获取完全交给页面 useAsyncData：
 *   emit('query', {page,pageSize,search,sortBy,order}) → 页面调用真实 API → 回传 rows/total/state
 * Loading / Empty / Error / Retry / NoPermission / ServiceUnavailable 六态由 AsyncPanel 统一呈现；
 * 组件内部不吞错误、不回退 DEMO、不自行发起请求。
 *
 * 搜索区常驻：不放在 AsyncPanel 内部，空态 / 错误态下仍可改条件重查；
 * 空态统一提供「刷新 + 返回」，返回 = 清空全部筛选（并广播 filter-reset 让页面清高级筛选）后重查，
 * 没有生效筛选时按钮禁用，各页只需传 emptyText 定制文案。
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
    /** 是否显示多选列；默认关闭，其他页面行为不变 */
    selectable?: boolean
    /** 空态文案；各页只改文案，刷新 / 返回按钮由组件统一提供 */
    emptyText?: string
  }>(),
  { loading: false, state: 'ready', error: '', pageSize: 20, selectable: false, emptyText: '暂无符合条件的数据' }
)

const emit = defineEmits<{
  (e: 'query', payload: MrQuery): void
  (e: 'retry'): void
  (e: 'selection-change', rows: Record<string, unknown>[]): void
  /** 重置 / 空态「返回」前广播：页面据此清掉自己持有的页面级筛选（如日期区间、排序） */
  (e: 'filter-reset'): void
}>()

const page = ref(1)
const pageSizeModel = ref(props.pageSize)
const sortBy = ref('')
const order = ref('')
const searchModel = reactive<Record<string, unknown>>({})
const searchColumns = computed(() => props.columns.filter((c) => !!c.search))
const tableRef = ref<{ clearSelection: () => void } | null>(null)

function onSelectionChange(rows: Record<string, unknown>[]) {
  emit('selection-change', rows)
}

/** 分页 / 筛选 / 刷新后 rows 会替换，清空选择避免跨页残留对已不存在的行执行批量操作 */
watch(() => props.rows, () => {
  if (!props.selectable) return
  tableRef.value?.clearSelection()
  emit('selection-change', [])
})

function clearSelection() {
  tableRef.value?.clearSelection()
  emit('selection-change', [])
}

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

/**
 * 重置：清空搜索表单、排序、页码，并先广播 filter-reset，
 * 让页面清掉自己持有的高级筛选（日期区间 / 排序字段），再发起真实查询。
 * 空态「返回」复用同一逻辑：返回＝清空筛选回到全部数据。
 */
function reset() {
  initModel()
  sortBy.value = ''
  order.value = ''
  emit('filter-reset')
  search()
}

/** 是否存在生效的筛选（含排序）：决定空态「返回」是否可用，避免点了也不会变 */
const hasActiveFilter = computed(() => {
  const dirty = Object.values(searchModel).some((v) => {
    if (v === null || v === undefined) return false
    if (Array.isArray(v)) return v.some((x) => x !== null && x !== undefined && String(x).trim() !== '')
    return String(v).trim() !== ''
  })
  return dirty || Boolean(sortBy.value || order.value)
})

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

defineExpose({ refresh, search, reset, clearSelection })

onMounted(emitQuery)
</script>
