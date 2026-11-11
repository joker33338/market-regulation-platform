<template>
  <div class="mr-pro-table">
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
      <template #empty>
        <slot name="empty"><span class="mr-pro-empty">暂无符合条件的数据</span></slot>
      </template>
    </el-table>

    <div class="mr-pro-pager">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next, jumper"
        background
        @current-change="load"
        @size-change="onSizeChange"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

/**
 * 轻量 MrProTable —— 借鉴 Geeker Admin ProTable 的交互骨架：
 *   columns 配置 → 自动生成搜索表单；fetcher 契约 { page, pageSize, ...params } → { list, total }
 * 保留 search() 重置到第一页、reset() 恢复默认、sizeChange 回到第一页、工具区与空态插槽。
 * 砍掉拖拽排序（sortablejs）、列设置持久化、多级表头、i18n，避免无意义依赖与整套模板替换。
 */
interface SearchOption { label: string; value: string | number }
interface ColumnSearch {
  el: 'input' | 'select' | 'dateRange'
  placeholder?: string
  options?: SearchOption[]
  defaultValue?: unknown
}
interface MrColumn {
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
interface FetchParams {
  page: number
  pageSize: number
  sortBy?: string
  order?: string
  [key: string]: unknown
}
type Row = Record<string, unknown>
type MrFetcher = (params: FetchParams) => Promise<{ list: Row[]; total: number }>

const props = defineProps<{
  columns: MrColumn[]
  fetcher: MrFetcher
  pageSize?: number
}>()

const rows = ref<Row[]>([])
const total = ref(0)
const loading = ref(false)
const page = ref(1)
const pageSize = ref(props.pageSize ?? 10)
const sortBy = ref('')
const order = ref('')
const searchModel = reactive<Record<string, unknown>>({})

const searchColumns = computed(() => props.columns.filter((c) => !!c.search))

function initModel() {
  for (const c of props.columns) {
    if (c.search) {
      searchModel[c.prop] = c.search.defaultValue ?? (c.search.el === 'dateRange' ? null : '')
    }
  }
}
initModel()

async function load() {
  loading.value = true
  try {
    const res = await props.fetcher({
      ...searchModel,
      page: page.value,
      pageSize: pageSize.value,
      sortBy: sortBy.value || undefined,
      order: order.value || undefined
    })
    rows.value = res.list || []
    total.value = res.total || 0
  } catch {
    rows.value = []
    total.value = 0
    ElMessage.warning('数据加载失败，请检查后端服务与筛选条件')
  } finally {
    loading.value = false
  }
}

function search() {
  page.value = 1
  load()
}

function reset() {
  initModel()
  sortBy.value = ''
  order.value = ''
  search()
}

function onSizeChange() {
  page.value = 1
  load()
}

function onSortChange(payload: { prop?: string; order?: string | null }) {
  sortBy.value = payload.prop || ''
  order.value = payload.order === 'ascending' ? 'asc' : payload.order === 'descending' ? 'desc' : ''
  load()
}

function refresh() {
  load()
}

defineExpose({ refresh, search, reset, rows })

onMounted(load)
</script>
