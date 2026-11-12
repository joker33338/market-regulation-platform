<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h1 class="page-title">文档管理</h1>
        <p class="page-desc">法规原始文件上传与全生命周期管理（原始证据文件只读，前端不可修改）</p>
      </div>
      <div class="header-tags">
        <el-tag type="success" effect="plain">真实接口 /api/documents</el-tag>
        <el-tag :type="contractTagType" effect="plain">{{ contractLabel[contractState] }}</el-tag>
      </div>
    </div>

    <el-alert type="info" :closable="false" class="contract-note"
      title="筛选与列表均以后端契约为准"
      :description="v023Filters
        ? '运行期已加载 v0.2.3 查询能力：除 page / page_size / keyword / status / doc_type 外，支持 date_from / date_to（必须带时区的闭区间）与 sort_by / order 白名单排序（同值按 file_id 稳定分页）。高级筛选只发契约允许字段，非法区间与非法排序由后端返回 422。'
        : '当前运行期契约仅支持 page、page_size、keyword、status、doc_type；v0.2.3 的日期区间与排序参数未加载，故本页不提供这两个筛选器，也不向后端发送额外字段。SHA256、状态、解析次数、上传时间来源标记均由后端返回。'" />

    <!-- 上传区：POST /api/parse/files，body 为原始二进制流 -->
    <el-card shadow="never" class="upload-card">
      <el-upload drag multiple :show-file-list="false" :http-request="doUpload" :accept="ACCEPT">
        <el-icon size="40" color="var(--mr-primary)"><UploadFilled /></el-icon>
        <div class="el-upload__text">将文件拖到此处，或 <em>点击上传</em></div>
        <div class="el-upload__tip">
          支持 PDF / Word(.docx) / 图片(.png/.jpg/.jpeg)；单文件 ≤100MB；单次最多 20 个。
          文件头魔数预校验，SHA256 以<b>后端返回</b>为准；上传结果只以后端真实响应判定，不使用定时器伪造成功。
        </div>
      </el-upload>

      <div v-if="uploadQueue.length" class="upload-queue">
        <div class="queue-summary">
          批量上传：{{ uploadDone }}/{{ uploadQueue.length }} 个文件，共 {{ formatSize(totalQueueSize) }}
          <el-button text size="small" @click="uploadQueue = []">清空列表</el-button>
        </div>
        <div v-for="item in uploadQueue" :key="item.uid" class="queue-item">
          <span class="queue-name" :title="item.message || item.name">
            {{ item.name }}
            <el-tag v-if="item.error" size="small" type="danger" effect="plain">失败</el-tag>
          </span>
          <el-progress :percentage="item.percent" :status="item.error ? 'exception' : undefined" style="flex: 1" :stroke-width="8" />
          <span class="num queue-size">{{ formatSize(item.size) }}</span>
          <span v-if="item.message" class="queue-msg">{{ item.message }}</span>
        </div>
      </div>
    </el-card>

    <!-- 本次会话真实上传：SHA256 / file_id 全部来自后端 -->
    <el-card v-if="realUploads.length" shadow="never" style="margin-top: 16px">
      <template #header>
        <div class="card-head">
          <span>本次会话真实上传 <span class="real-badge">REAL</span></span>
          <div class="card-actions">
            <span class="card-sub">来自 POST /api/parse/files 的真实响应 · 创建成功后自动移出待创建列表</span>
            <el-button v-if="selectedUploads.length" size="small" type="danger" plain @click="removeSelectedUploads">
              移出待创建（{{ selectedUploads.length }}）
            </el-button>
            <el-tooltip :disabled="bulkCreatable" :content="bulkHint" placement="top">
              <span>
                <el-button size="small" type="primary" :loading="bulkSubmitting" :disabled="!bulkCreatable" @click="createTasksForAll">
                  一键解析全部（{{ realUploads.length }}）
                </el-button>
              </span>
            </el-tooltip>
          </div>
        </div>
      </template>
      <el-table ref="uploadTableRef" :data="realUploads" size="small" max-height="200" @selection-change="onUploadSelectionChange">
        <el-table-column type="selection" width="46" />
        <el-table-column prop="name" label="文件名称" min-width="220" show-overflow-tooltip />
        <el-table-column label="大小" width="100" align="right">
          <template #default="{ row }"><span class="num">{{ formatSize(row.bytes) }}</span></template>
        </el-table-column>
        <el-table-column label="SHA256（后端返回）" min-width="220">
          <template #default="{ row }"><code class="sha">{{ row.sha256 }}</code></template>
        </el-table-column>
        <el-table-column prop="at" label="上传时间" width="160" />
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button text size="small" type="primary" :loading="submittingId === row.fileId" :disabled="!hasAuth || submittingId !== '' || bulkSubmitting" @click="createTaskFor(row)">
              创建解析任务
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <div v-if="!hasAuth" class="mr-disabled-hint" style="margin-top: 8px">
        未配置 API Token：请在系统监控页配置后，方可调用上传与创建任务接口。
      </div>
    </el-card>

    <!-- 创建回执放在卡片外：待创建列表清空后仍可见，避免误以为任务没有创建成功 -->
    <div v-if="lastTask" class="created-task-note">
      <el-alert type="success" :closable="false"
        :title="`解析任务已创建：${lastTask.task_id}（状态 ${lastTask.status}）— 本次会话累计创建 ${createdTaskCount} 个`"
        description="收到后端真实回执后，创建成功的文件已从上方「本次会话真实上传」待创建列表移除；同一上传项始终复用同一 Idempotency-Key，重复点击或网络重试不会重复建任务。确需重跑请使用下方文档列表的「重新解析」（这是显式的新任务）。" />
      <el-button text size="small" type="primary" @click="gotoTask(lastTask.task_id)">到智能解析中心查看真实进度 →</el-button>
    </div>

    <!-- 文档列表：真实 GET /api/documents，MrProTable 受控模式 -->
    <el-card shadow="never" style="margin-top: 16px">
      <template #header>
        <div class="card-head">
          <span>文档列表 <span class="real-badge">REAL</span></span>
          <span class="card-sub">数据源：{{ listSource }}</span>
        </div>
      </template>
      <!-- v0.2.3 高级筛选：只在运行期契约确认具备 date_from/date_to/sort_by/order 时出现 -->
      <div v-if="v023Filters" class="advanced-filter">
        <span class="af-label">上传时间（闭区间 · 自动带时区）</span>
        <el-date-picker v-model="dateRange" type="datetimerange" size="small"
          start-placeholder="开始时间" end-placeholder="结束时间" style="width: 350px" />
        <span class="af-label">排序字段</span>
        <el-select v-model="sortBy" size="small" placeholder="默认 uploaded_at" style="width: 150px">
          <el-option label="上传时间" value="uploaded_at" />
          <el-option label="文件名" value="file_name" />
          <el-option label="文件大小" value="size_bytes" />
          <el-option label="状态" value="status" />
        </el-select>
        <el-select v-model="order" size="small" style="width: 100px">
          <el-option label="降序" value="desc" />
          <el-option label="升序" value="asc" />
        </el-select>
        <el-button size="small" type="primary" @click="applyAdvanced">应用</el-button>
        <el-button size="small" @click="resetAdvanced">重置</el-button>
      </div>

      <div v-if="selectedRows.length" class="batch-bar">
        <span>已选 <b>{{ selectedRows.length }}</b> 项（仅当前页，翻页 / 查询 / 刷新后自动清空）</span>
        <el-button size="small" @click="clearTableSelection">取消选择</el-button>
        <el-button size="small" type="primary" plain :loading="batchBusy" :disabled="!hasAuth || batchBusy" @click="batchDownload">
          批量下载原件
        </el-button>
        <el-tooltip :disabled="canDeleteDocuments" :content="deleteDisabledHint" placement="top">
          <span>
            <el-button size="small" type="danger" plain :disabled="!canDeleteDocuments || batchBusy" @click="deleteSelected">
              删除选中（{{ selectedRows.length }}）
            </el-button>
          </span>
        </el-tooltip>
      </div>
      <el-alert v-if="!canDeleteDocuments" type="warning" :closable="false" class="delete-note"
        title="删除功能需后端接口：当前运行期契约未提供 DELETE /api/documents/{file_id}"
        description="原始文件为只读证据，前端不会本地隐藏行来假装删除成功。多选与批量下载原件现在即可使用；待后端实现并在 /api/openapi.json 声明该 DELETE 方法后，删除按钮自动解锁，并按真实回执刷新列表。" />

      <MrProTable
        ref="tableRef"
        selectable
        :columns="columns"
        :rows="tableRows"
        :total="tableTotal"
        :loading="list.loading.value"
        :state="list.state.value"
        :error="list.error.value"
        @query="onQuery"
        @retry="list.load()"
        @selection-change="onSelectionChange"
      >
        <template #col-size_bytes="{ row }"><span class="num">{{ formatSize(Number(row.size_bytes)) }}</span></template>
        <template #col-status="{ row }"><StatusTag :status="String(row.status)" /></template>
        <template #col-sha256="{ row }"><code class="sha">{{ shortSha(String(row.sha256)) }}</code></template>
        <template #col-uploaded_at="{ row }">
          <span>{{ formatTime(String(row.uploaded_at)) }}</span>
          <el-tooltip v-if="row.uploaded_at_source === 'metadata_mtime'" content="历史上传缺乏显式时间戳，此为元数据修改时间，非确证上传时间" placement="top">
            <el-tag size="small" type="warning" effect="plain" style="margin-left: 6px">元数据时间</el-tag>
          </el-tooltip>
        </template>
        <template #extra-columns>
          <el-table-column label="操作" width="330" fixed="right">
            <template #default="{ row }">
              <el-button text size="small" type="primary" @click="openDetail(row)">详情</el-button>
              <el-button text size="small" :loading="downloadingId === row.file_id" :disabled="!hasAuth || downloadingId !== ''" @click="download(row)">下载原件</el-button>
              <el-button text size="small" :loading="submittingId === row.file_id" :disabled="!hasAuth || submittingId !== ''" @click="reparse(row)">重新解析</el-button>
              <el-button text size="small" :disabled="!row.latest_task_id" @click="viewResults(row)">解析结果</el-button>
              <el-tooltip :disabled="canDeleteDocuments" :content="deleteDisabledHint" placement="top">
                <span>
                  <el-button text size="small" type="danger" :disabled="!canDeleteDocuments || batchBusy" @click="deleteOne(row)">删除</el-button>
                </span>
              </el-tooltip>
            </template>
          </el-table-column>
        </template>
        <template #empty>
          <el-empty :image-size="70" description="当前筛选条件下没有文档记录（后端返回空列表，非演示数据）">
            <div class="empty-actions">
              <el-button size="small" @click="list.load()">刷新</el-button>
              <el-tooltip :content="hasActiveFilter
                ? '清空筛选条件（搜索词 / 状态 / 类型 / 时间区间 / 排序），返回全部文档'
                : '当前没有生效的筛选条件，后端返回的就是全部文档，无需返回'" placement="top">
                <span>
                  <el-button size="small" :disabled="!hasActiveFilter" @click="backToAll">返回</el-button>
                </span>
              </el-tooltip>
            </div>
          </el-empty>
        </template>
      </MrProTable>
    </el-card>

    <!-- 详情抽屉：真实 GET /api/documents/{id} + /parse-history -->
    <el-drawer v-model="drawer" title="文件详情" size="620px">
      <AsyncPanel :state="detail.state.value" :error="detail.error.value" @retry="detail.load()">
        <template v-if="detail.data.value">
          <el-descriptions :column="1" border>
            <el-descriptions-item label="文件名称">{{ detail.data.value.file_name }}</el-descriptions-item>
            <el-descriptions-item label="文档类型">{{ detail.data.value.doc_type }}</el-descriptions-item>
            <el-descriptions-item label="文件大小">{{ formatSize(detail.data.value.size_bytes) }}</el-descriptions-item>
            <el-descriptions-item label="上传时间">{{ formatTime(detail.data.value.uploaded_at) }}（{{ uploadedAtLabel(detail.data.value.uploaded_at_source) }}）</el-descriptions-item>
            <el-descriptions-item label="状态"><StatusTag :status="detail.data.value.status" /></el-descriptions-item>
            <el-descriptions-item label="关联任务">{{ detail.data.value.latest_task_id || '—' }}</el-descriptions-item>
            <el-descriptions-item label="解析次数"><span class="num">{{ detail.data.value.parse_count }}</span></el-descriptions-item>
            <el-descriptions-item label="SHA256（后端）">
              <code class="sha">{{ detail.data.value.sha256 }}</code>
              <el-button text size="small" type="primary" @click="copySha(detail.data.value?.sha256 || '')">复制</el-button>
            </el-descriptions-item>
          </el-descriptions>
        </template>
      </AsyncPanel>

      <el-divider content-position="left">关联 OCR 解析历史（真实 GET /parse-history）</el-divider>
      <AsyncPanel :state="history.state.value" :error="history.error.value" empty-text="该文档尚无关联解析任务" @retry="history.load()">
        <el-table :data="history.data.value?.list || []" size="small" max-height="240">
          <el-table-column label="任务 ID" min-width="140" show-overflow-tooltip>
            <template #default="{ row }"><code class="sha">{{ row.task.task_id }}</code></template>
          </el-table-column>
          <el-table-column label="状态" width="100"><template #default="{ row }"><StatusTag :status="row.task.status" /></template></el-table-column>
          <el-table-column label="引擎（后端）" width="130"><template #default="{ row }">{{ engineOf(row.task) }}</template></el-table-column>
          <el-table-column label="开始时间" width="150"><template #default="{ row }">{{ formatTime(row.task.created_at) }}</template></el-table-column>
          <el-table-column label="耗时" width="90" align="right"><template #default="{ row }">{{ row.elapsed_seconds == null ? '—' : row.elapsed_seconds + 's' }}</template></el-table-column>
          <el-table-column label="操作" width="90" fixed="right">
            <template #default="{ row }"><el-button text size="small" type="primary" @click="gotoTask(row.task.task_id)">查看</el-button></template>
          </el-table-column>
        </el-table>
        <div class="drawer-pager">
          <el-pagination
            v-model:current-page="historyPage"
            :page-size="historyPageSize"
            :total="history.data.value?.total || 0"
            layout="total, prev, pager, next"
            small background
            @current-change="history.load()"
          />
        </div>
      </AsyncPanel>

      <el-alert type="info" :closable="false" style="margin-top: 14px"
        title="原始文件为只读证据"
        description="解析结果与原始文件通过后端 SHA256 绑定；下载字节来自按当前 principal 与业务 owner 范围隔离的 /source 接口，前端不修改原始文件、不绕过后端权限。" />
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import type { UploadRequestOptions } from 'element-plus'
import StatusTag from '@/components/StatusTag.vue'
import MrProTable, { type MrColumn, type MrQuery } from '@/components/MrProTable.vue'
import AsyncPanel from '@/components/AsyncPanel.vue'
import { useAsyncData } from '@/composables/useAsyncData'
import { hasToken } from '@/api/client'
import { apiErrorHint, notifyApiError, toApiError } from '@/api/errors'
import {
  contractState, contractLabel, hasV023DocumentFilters,
  hasRuntimeMethod, unimplementedHint
} from '@/api/dataSource'
import { downloadSourceFile } from '@/api/documentFiles'
import { deleteDocument, getDocument, getDocumentHistory, listDocuments } from '@/api/frontend'
import { uploadFile, createParseTask, UPLOAD_LIMIT_BYTES, UPLOAD_ALLOWED_EXT, MAX_FILES_PER_TASK } from '@/api/parse'
import type { DocumentInfo, DocumentList, DocumentQuery, ParseHistory, ParseTask } from '@/api/types'

const router = useRouter()
const ACCEPT = UPLOAD_ALLOWED_EXT.join(',')
const hasAuth = computed(() => hasToken())
const contractTagType = computed(() => (contractState.value === 'ready' ? 'success' : 'warning'))

/* ───────── 真实文档列表（受控 MrProTable） ───────── */
const query = ref<DocumentQuery>({ page: 1, pageSize: 20, keyword: '', status: '', docType: '' })
const list = useAsyncData<DocumentList>((signal) => listDocuments(query.value, signal), { immediate: false })

/* v0.2.3 高级筛选：运行期契约未加载时不渲染控件，也不发 date_from/date_to/sort_by/order */
const v023Filters = computed(() => hasV023DocumentFilters())
const dateRange = ref<Date[] | null>(null)
const sortBy = ref<DocumentQuery['sortBy']>('')
const order = ref<DocumentQuery['order']>('')
function applyAdvanced() {
  const d = dateRange.value
  query.value = {
    ...query.value,
    page: 1,
    dateFrom: d?.[0] ? new Date(d[0]).toISOString() : '',
    dateTo: d?.[1] ? new Date(d[1]).toISOString() : '',
    sortBy: sortBy.value,
    order: order.value
  }
  void list.load()
}
function resetAdvanced() {
  dateRange.value = null
  sortBy.value = ''
  order.value = ''
  query.value = { ...query.value, page: 1, dateFrom: '', dateTo: '', sortBy: '', order: '' }
  void list.load()
}

/**
 * 空态「返回」：把当前生效的筛选条件全部清掉，回到未筛选的全部文档。
 * 只重置前端查询参数并重新请求真实接口，不做本地补数据、不伪造结果；
 * 没有生效筛选条件时按钮禁用（此时后端返回的就是全部文档的真实空态）。
 */
const hasActiveFilter = computed(() => {
  const q = query.value
  if (q.keyword || q.status || q.docType) return true
  return v023Filters.value ? Boolean(q.dateFrom || q.dateTo || q.sortBy || q.order) : false
})

function backToAll() {
  if (!hasActiveFilter.value) return
  dateRange.value = null
  sortBy.value = ''
  order.value = ''
  query.value = { page: 1, pageSize: query.value.pageSize, keyword: '', status: '', docType: '' }
  if (v023Filters.value) query.value = { ...query.value, dateFrom: '', dateTo: '', sortBy: '', order: '' }
  clearTableSelection()
  // reset() 会同时清空搜索表单、排序与页码并重新发起真实查询
  if (tableRef.value) tableRef.value.reset()
  else void list.load()
}

const tableRows = computed(() => (list.data.value?.list || []) as unknown as Record<string, unknown>[])
const tableTotal = computed(() => list.data.value?.total || 0)
const listSource = computed(() => list.data.value?.source || 'owner_upload_metadata+sqlite.parse_tasks')

const columns: MrColumn[] = [
  { prop: 'file_name', label: '文件名称', minWidth: 240, showOverflowTooltip: true, search: { el: 'input', placeholder: '搜索文件名称（keyword）' } },
  { prop: 'doc_type', label: '类型', width: 90, search: { el: 'select', placeholder: '文档类型', options: [
    { label: 'PDF', value: 'pdf' }, { label: 'Word', value: 'docx' }, { label: '图片', value: 'image' }
  ] } },
  { prop: 'status', label: '解析状态', width: 120, search: { el: 'select', placeholder: '解析状态', options: [
    { label: '仅上传', value: 'uploaded' }, { label: '待复核', value: 'pending_review' },
    { label: '等待中', value: 'pending' }, { label: '执行中', value: 'running' },
    { label: '已完成', value: 'completed' }, { label: '部分成功', value: 'partial' },
    { label: '失败', value: 'failed' }, { label: '已取消', value: 'canceled' }, { label: '超时', value: 'timed_out' }
  ] } },
  { prop: 'size_bytes', label: '大小', width: 100, align: 'right' },
  { prop: 'uploaded_at', label: '上传时间', width: 190 },
  { prop: 'parse_count', label: '解析次数', width: 90, align: 'right' },
  { prop: 'sha256', label: 'SHA256', width: 150 },
  { prop: 'latest_task_id', label: '关联任务', width: 140, showOverflowTooltip: true }
]

function onQuery(q: MrQuery) {
  query.value = {
    page: q.page,
    pageSize: q.pageSize,
    keyword: String(q.search.file_name || ''),
    status: String(q.search.status || ''),
    docType: (String(q.search.doc_type || '') || '') as DocumentQuery['docType'],
    dateFrom: v023Filters.value ? query.value.dateFrom : undefined,
    dateTo: v023Filters.value ? query.value.dateTo : undefined,
    sortBy: v023Filters.value ? query.value.sortBy : undefined,
    order: v023Filters.value ? query.value.order : undefined
  }
  void list.load()
}

/* ───────── 详情与解析历史 ───────── */
const drawer = ref(false)
const currentFileId = ref('')
const historyPage = ref(1)
const historyPageSize = 20
const detail = useAsyncData<DocumentInfo>((signal) => getDocument(currentFileId.value, signal), { immediate: false })
const history = useAsyncData<ParseHistory>(
  (signal) => getDocumentHistory(currentFileId.value, { page: historyPage.value, pageSize: historyPageSize }, signal),
  { immediate: false }
)

function openDetail(row: Record<string, unknown>) {
  currentFileId.value = String(row.file_id || '')
  historyPage.value = 1
  drawer.value = true
  void detail.load()
  void history.load()
}

function engineOf(task: ParseTask): string {
  const engines = task.files?.map((f) => f.selected_engine).filter(Boolean) || []
  if (!engines.length) return '—'
  return engines.map((e) => (Array.isArray(e) ? e.join('/') : String(e))).join('、')
}

/* ───────── 操作：全部走真实接口 ───────── */
const downloadingId = ref('')
const submittingId = ref('')
const lastTask = ref<ParseTask | null>(null)
const createdTaskCount = ref(0)

/* ───────── 多选与删除 ─────────
 * 多选列 / 批量下载是真实可用能力；删除按「方法级」运行期门控：
 * /api/documents/{file_id} 只有 GET，路径存在不代表 DELETE 可用，
 * 因此必须比对 /api/openapi.json 里的 HTTP 方法声明，绝不本地隐藏行伪造删除成功。
 */
const DELETE_DOCUMENT_PATH = '/api/documents/{file_id}'
const tableRef = ref<{ clearSelection: () => void; reset: () => void } | null>(null)
const selectedRows = ref<Record<string, unknown>[]>([])
const batchBusy = ref(false)

const canDeleteDocuments = computed(() => hasToken() && hasRuntimeMethod('DELETE', DELETE_DOCUMENT_PATH))
const deleteDisabledHint = computed(() => hasToken()
  ? unimplementedHint(`DELETE ${DELETE_DOCUMENT_PATH}`)
  : '请先在系统监控页配置 API Token')

function onSelectionChange(rows: Record<string, unknown>[]) {
  selectedRows.value = rows
}
function clearTableSelection() {
  tableRef.value?.clearSelection()
  selectedRows.value = []
}

/** 批量下载走真实 GET /source，逐个字节下载；任一失败如实计数，不吞错 */
async function batchDownload() {
  if (!hasAuth.value || batchBusy.value || !selectedRows.value.length) return
  batchBusy.value = true
  let ok = 0
  const failed: string[] = []
  try {
    for (const row of selectedRows.value) {
      const id = String(row.file_id || '')
      const name = String(row.file_name || id)
      if (!id) continue
      try {
        await downloadSourceFile(id, name)
        ok += 1
      } catch {
        failed.push(name)
      }
    }
    if (ok) ElMessage.success(`已发起 ${ok} 个原件下载${failed.length ? `，${failed.length} 个失败` : ''}`)
    if (failed.length) ElMessage.warning(`下载失败：${failed.slice(0, 3).join('、')}${failed.length > 3 ? ' 等' : ''}`)
  } finally {
    batchBusy.value = false
  }
}

async function confirmDelete(count: number): Promise<boolean> {
  return ElMessageBox.confirm(
    `将对 ${count} 个文档调用真实 DELETE 接口。原始文件是只读证据，删除须由后端授权并执行；前端不会隐藏列表行来伪造成功，结果以刷新后的列表为准。`,
    '确认删除文档',
    { type: 'warning', confirmButtonText: '提交删除请求', cancelButtonText: '取消' }
  ).then(() => true).catch(() => false)
}

/** 仅按后端真实响应计数：2xx 视为「请求被接受」，随后重新拉取列表确认，不本地移除行 */
async function submitDeletes(rows: Record<string, unknown>[]) {
  batchBusy.value = true
  let accepted = 0
  const rejected: string[] = []
  try {
    for (const row of rows) {
      const id = String(row.file_id || '')
      const name = String(row.file_name || id)
      if (!id) continue
      try {
        await deleteDocument(id)
        accepted += 1
      } catch (err) {
        rejected.push(`${name}：${apiErrorHint(err)}`)
      }
    }
    if (accepted) ElMessage.success(`后端已接受 ${accepted} 个删除请求，正在刷新列表确认`)
    if (rejected.length) ElMessage.warning(`${rejected.length} 个删除请求失败：${rejected.slice(0, 2).join('；')}`)
    void list.load()
  } finally {
    batchBusy.value = false
    clearTableSelection()
  }
}

async function deleteSelected() {
  if (!canDeleteDocuments.value || batchBusy.value || !selectedRows.value.length) return
  const rows = [...selectedRows.value]
  if (!(await confirmDelete(rows.length))) return
  await submitDeletes(rows)
}

async function deleteOne(row: Record<string, unknown>) {
  if (!canDeleteDocuments.value || batchBusy.value) return
  if (!(await confirmDelete(1))) return
  await submitDeletes([row])
}

async function download(row: Record<string, unknown>) {
  const id = String(row.file_id || '')
  const name = String(row.file_name || id)
  if (!id || !hasAuth.value) return
  downloadingId.value = id
  try {
    await downloadSourceFile(id, name)
    ElMessage.success(`已下载原始文件：${name}`)
  } catch (err) {
    notifyApiError(err, '原始文件下载失败')
  } finally {
    downloadingId.value = ''
  }
}

async function reparse(row: Record<string, unknown>) {
  const id = String(row.file_id || '')
  if (!id || !hasAuth.value || submittingId.value) return
  submittingId.value = id
  try {
    // 「重新解析」是用户显式发起的新任务，每次点按都用新键；请求期间由 submittingId 防连点
    const task = await createParseTask({ file_ids: [id] }, crypto.randomUUID())
    lastTask.value = task
    createdTaskCount.value += 1
    ElMessage.success(`已创建解析任务 ${task.task_id}`)
    void list.load()
  } catch (err) {
    notifyApiError(err, '创建解析任务失败')
  } finally {
    submittingId.value = ''
  }
}

function viewResults(row: Record<string, unknown>) {
  const id = String(row.latest_task_id || '')
  if (id) gotoTask(id)
  else ElMessage.info('该文档尚无关联解析任务')
}

function gotoTask(taskId: string) {
  drawer.value = false
  void router.push({ path: '/parsing', query: { task: taskId } })
}

function copySha(value: string) {
  if (value) {
    void navigator.clipboard.writeText(value)
    ElMessage.success('SHA256 已复制')
  }
}

/* ───────── 上传（复用旧接口，结果只以后端响应为准） ───────── */
interface QueueItem { uid: string; name: string; size: number; percent: number; error: boolean; message?: string }
interface RealUpload {
  fileId: string; name: string; sha256: string; bytes: number; at: string
  /** 该上传项在整个会话里复用同一幂等键：同键同请求由后端返回原任务，不会重复创建 */
  idempotencyKey: string
}

const uploadQueue = ref<QueueItem[]>([])
const realUploads = ref<RealUpload[]>([])
const uploadedHashes = new Set<string>()

/* 上传项多选：只清理本地「待创建」队列，不触碰后端已上传的原始文件与已创建任务 */
const uploadTableRef = ref<{ clearSelection: () => void } | null>(null)
const selectedUploads = ref<RealUpload[]>([])
function onUploadSelectionChange(rows: RealUpload[]) {
  selectedUploads.value = rows
}

async function removeSelectedUploads() {
  const ids = new Set(selectedUploads.value.map((i) => i.fileId))
  if (!ids.size) return
  try {
    await ElMessageBox.confirm(
      `仅从「本次会话真实上传」待创建列表移除 ${ids.size} 项，不会删除后端已上传的原始文件，也不会取消已创建的解析任务。`,
      '移出待创建列表',
      { type: 'info', confirmButtonText: '确认移出', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  realUploads.value = realUploads.value.filter((i) => !ids.has(i.fileId))
  selectedUploads.value = []
  uploadTableRef.value?.clearSelection()
  ElMessage.success(`已移出 ${ids.size} 项待创建文件`)
}

/* ───────── 一键解析全部：一次 POST 提交多个 file_id（后端单任务上限 20） ───────── */
const bulkSubmitting = ref(false)
/** 待创建列表不变时复用同一键与同一 body；列表变化（新增/移除文件）才作为新操作换键 */
const bulkRequest = ref<{ signature: string; key: string } | null>(null)
const bulkCreatable = computed(() =>
  hasAuth.value && realUploads.value.length > 0 &&
  realUploads.value.length <= MAX_FILES_PER_TASK &&
  !submittingId.value && !bulkSubmitting.value
)
const bulkHint = computed(() => {
  if (!hasAuth.value) return '请先在系统监控页配置 API Token'
  if (!realUploads.value.length) return '暂无待创建解析任务的上传文件'
  if (realUploads.value.length > MAX_FILES_PER_TASK) {
    return `待创建 ${realUploads.value.length} 个文件，超过单任务上限 ${MAX_FILES_PER_TASK} 个；请先逐个创建或减少待创建项`
  }
  if (submittingId.value || bulkSubmitting.value) return '正在创建解析任务，请稍候'
  return ''
})
const uploadDone = computed(() => uploadQueue.value.filter((i) => i.percent >= 100 || i.error).length)
const totalQueueSize = computed(() => uploadQueue.value.reduce((s, i) => s + i.size, 0))

function formatSize(bytes: number): string {
  if (!Number.isFinite(bytes)) return '—'
  if (bytes >= 1048576) return (bytes / 1048576).toFixed(1) + ' MB'
  if (bytes >= 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return bytes + ' B'
}
function shortSha(v: string) { return v ? v.slice(0, 12) + '…' : '—' }
function formatTime(v: string) { return v ? v.replace('T', ' ').slice(0, 19) : '—' }
function uploadedAtLabel(v: string) { return v === 'upload_metadata' ? '确证上传时间' : '元数据修改时间（非确证上传时间）' }
function extOf(name: string): string {
  const i = name.lastIndexOf('.')
  return i < 0 ? '' : name.slice(i).toLowerCase()
}

async function magicOk(file: File): Promise<boolean> {
  const ext = extOf(file.name)
  const b = new Uint8Array(await file.slice(0, 8).arrayBuffer())
  const starts = (arr: number[]) => arr.every((v, i) => b[i] === v)
  if (ext === '.pdf') return starts([0x25, 0x50, 0x44, 0x46])
  if (ext === '.png') return starts([0x89, 0x50, 0x4e, 0x47])
  if (ext === '.jpg' || ext === '.jpeg') return starts([0xff, 0xd8, 0xff])
  if (ext === '.docx') return starts([0x50, 0x4b, 0x03, 0x04])
  return false
}

async function localSha256(file: File): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', await file.arrayBuffer())
  return Array.from(new Uint8Array(digest)).map((x) => x.toString(16).padStart(2, '0')).join('')
}

function fail(item: QueueItem, message: string, notify = true) {
  item.error = true
  item.message = message
  if (notify) ElMessage.warning(message)
}

async function doUpload(options: UploadRequestOptions) {
  const file = options.file as File
  const item = reactive<QueueItem>({
    uid: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
    name: file.name, size: file.size, percent: 0, error: false
  })
  if (uploadQueue.value.length >= MAX_FILES_PER_TASK) {
    fail(item, `单次最多上传 ${MAX_FILES_PER_TASK} 个文件`)
    uploadQueue.value.push(item)
    return
  }
  uploadQueue.value.push(item)
  if (!UPLOAD_ALLOWED_EXT.includes(extOf(file.name) as (typeof UPLOAD_ALLOWED_EXT)[number])) {
    return fail(item, `不支持的格式 ${extOf(file.name) || '(无扩展名)'}，仅支持 PDF / DOCX / PNG / JPG / JPEG`)
  }
  if (file.size > UPLOAD_LIMIT_BYTES) return fail(item, `文件超过 100MB 上限（${formatSize(file.size)}）`)
  if (!(await magicOk(file))) return fail(item, '文件头与扩展名不符，可能被重命名或损坏；后端会拒绝该请求')
  if (!hasToken()) return fail(item, '未配置 API Token，请在系统监控页配置后再上传')

  let localHash = ''
  try { localHash = await localSha256(file) } catch { /* 浏览器不支持 WebCrypto 时跳过重复识别 */ }
  if (localHash && uploadedHashes.has(localHash)) {
    return fail(item, '检测到重复文件（SHA256 与本次会话已上传文件相同），已跳过')
  }
  try {
    const res = await uploadFile(file, (p) => { item.percent = p })
    item.percent = 100
    if (localHash) uploadedHashes.add(localHash)
    if (localHash && localHash !== res.sha256) item.message = '提示：前端计算值与后端返回值不一致，请核对文件内容'
    realUploads.value.unshift({
      fileId: res.file_id, name: file.name, sha256: res.sha256, bytes: res.bytes,
      at: new Date().toLocaleString('zh-CN'),
      idempotencyKey: crypto.randomUUID()
    })
    ElMessage.success(`${file.name} 上传成功，SHA256 由后端返回`)
    void list.load()
  } catch (err) {
    notifyApiError(err, '上传失败')
    fail(item, apiErrorHint(err), false)
  }
}

/** 409 = 同键异请求；其余按统一错误模型提示。失败一律保留待创建项，允许同键重试 */
function reportCreateFailure(err: unknown, fallback: string) {
  const e = toApiError(err)
  if (e.status === 409) {
    ElMessage.error('创建被拒绝（409）：同一幂等键对应了不同请求，已刷新文档列表，请确认后再试。')
    void list.load()
  } else {
    notifyApiError(err, fallback)
  }
}

async function createTaskFor(row: RealUpload) {
  if (submittingId.value || bulkSubmitting.value || !hasAuth.value) return
  submittingId.value = row.fileId
  try {
    // 同一上传项固定同一键与同一 body：后端按 (owner, Idempotency-Key) + 请求指纹幂等，
    // 连点或网络重试都会返回原任务，不会新建第二条（旧实现每次随机键导致重复建任务）。
    const task = await createParseTask({ file_ids: [row.fileId] }, row.idempotencyKey)
    lastTask.value = task
    createdTaskCount.value += 1
    // 只有拿到后端真实回执才移出待创建列表，不在本地伪造「已完成」
    realUploads.value = realUploads.value.filter((i) => i.fileId !== row.fileId)
    ElMessage.success(`解析任务已创建：${task.task_id}`)
    void list.load()
  } catch (err) {
    reportCreateFailure(err, '创建解析任务失败')
  } finally {
    submittingId.value = ''
  }
}

async function createTasksForAll() {
  if (!bulkCreatable.value) return
  const ids = realUploads.value.map((r) => r.fileId)
  const signature = JSON.stringify(ids)
  const existing = bulkRequest.value
  const key = existing && existing.signature === signature ? existing.key : crypto.randomUUID()
  bulkRequest.value = { signature, key } // 列表不变则重试沿用同键同 body
  bulkSubmitting.value = true
  try {
    // 后端 POST /api/parse/tasks 支持一次提交 1–20 个 file_id，故整批只需一个真实任务
    const task = await createParseTask({ file_ids: ids }, key)
    lastTask.value = task
    createdTaskCount.value += 1
    const done = new Set(ids)
    realUploads.value = realUploads.value.filter((r) => !done.has(r.fileId))
    bulkRequest.value = null
    ElMessage.success(`已为 ${ids.length} 个文件创建解析任务：${task.task_id}`)
    void list.load()
  } catch (err) {
    reportCreateFailure(err, '一键解析失败')
  } finally {
    bulkSubmitting.value = false
  }
}
</script>

<style scoped>
.header-tags { display: flex; gap: 8px; align-items: center; }
.contract-note { margin-bottom: 12px; }
.upload-card :deep(.el-upload-dragger) { padding: 24px; }
.card-head { display: flex; justify-content: space-between; align-items: center; font-weight: 600; }
.card-actions { display: flex; align-items: center; gap: 12px; font-weight: 400; }
.card-sub { font-weight: 400; font-size: 12px; color: var(--mr-text-3); }
.created-task-note { margin-top: 16px; }
.upload-queue { margin-top: 16px; border-top: 1px dashed var(--mr-line); padding-top: 12px; }
.queue-summary { font-size: 13px; color: var(--mr-text-2); margin-bottom: 8px; display: flex; align-items: center; gap: 12px; }
.queue-item { display: flex; align-items: center; gap: 12px; margin: 6px 0; flex-wrap: wrap; }
.queue-name { width: 240px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 13px; }
.queue-size { width: 80px; text-align: right; color: var(--mr-text-3); font-size: 12px; }
.queue-msg { flex-basis: 100%; font-size: 12px; color: var(--mr-st-danger); }
.sha { font-size: 12px; word-break: break-all; color: var(--mr-text-2); }
.drawer-pager { margin-top: 10px; display: flex; justify-content: flex-end; }
/* v0.2.3 高级筛选：仅运行期契约确认具备参数时才渲染 */
.advanced-filter {
  display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
  padding: 10px 0 14px; margin-bottom: 4px; border-bottom: 1px dashed var(--mr-line);
}
.af-label { font-size: 12px; color: var(--mr-text-2); flex-shrink: 0; }
/* 多选批量操作条：选中后才出现，避免常态占用列表空间 */
.batch-bar {
  display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
  padding: 8px 12px; margin-bottom: 10px;
  border: 1px solid var(--mr-line); border-radius: 6px;
  background: var(--mr-bg-soft, transparent); font-size: 13px;
}
.batch-bar b { color: var(--mr-primary); }
.delete-note { margin-bottom: 10px; }
/* 空态操作：刷新 + 返回（返回＝清空筛选回到全部文档） */
.empty-actions { display: flex; align-items: center; justify-content: center; gap: 8px; }
</style>
