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
      description="GET /api/documents 仅支持 page、page_size、keyword、status、doc_type；后端明确不支持时间区间与任意排序，故本页不提供这两个筛选器，也不向后端发送额外字段。SHA256、状态、解析次数、上传时间来源标记均由后端返回。" />

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
          <span class="card-sub">来自 POST /api/parse/files 的真实响应</span>
        </div>
      </template>
      <el-table :data="realUploads" size="small">
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
            <el-button text size="small" type="primary" :loading="submittingId === row.fileId" :disabled="!hasAuth || submittingId !== ''" @click="createTaskFor(row)">
              创建解析任务
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-alert v-if="lastTask" type="success" :closable="false" style="margin-top: 12px"
        :title="`解析任务已创建：${lastTask.task_id}（状态 ${lastTask.status}）— 可到智能解析中心查看真实进度`" />
      <div v-if="!hasAuth" class="mr-disabled-hint" style="margin-top: 8px">
        未配置 API Token：请在系统监控页配置后，方可调用上传与创建任务接口。
      </div>
    </el-card>

    <!-- 文档列表：真实 GET /api/documents，MrProTable 受控模式 -->
    <el-card shadow="never" style="margin-top: 16px">
      <template #header>
        <div class="card-head">
          <span>文档列表 <span class="real-badge">REAL</span></span>
          <span class="card-sub">数据源：{{ listSource }}</span>
        </div>
      </template>
      <MrProTable
        :columns="columns"
        :rows="tableRows"
        :total="tableTotal"
        :loading="list.loading.value"
        :state="list.state.value"
        :error="list.error.value"
        @query="onQuery"
        @retry="list.load()"
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
          <el-table-column label="操作" width="270" fixed="right">
            <template #default="{ row }">
              <el-button text size="small" type="primary" @click="openDetail(row)">详情</el-button>
              <el-button text size="small" :loading="downloadingId === row.file_id" :disabled="!hasAuth || downloadingId !== ''" @click="download(row)">下载原件</el-button>
              <el-button text size="small" :loading="submittingId === row.file_id" :disabled="!hasAuth || submittingId !== ''" @click="reparse(row)">重新解析</el-button>
              <el-button text size="small" :disabled="!row.latest_task_id" @click="viewResults(row)">解析结果</el-button>
            </template>
          </el-table-column>
        </template>
        <template #empty>
          <el-empty :image-size="70" description="当前筛选条件下没有文档记录（后端返回空列表，非演示数据）">
            <el-button size="small" @click="list.load()">刷新</el-button>
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
        <el-table :data="history.data.value?.list || []" size="small">
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
        description="解析结果与原始文件通过后端 SHA256 绑定；下载字节来自 owner 隔离的 /source 接口，前端不修改原始文件、不绕过后端权限。" />
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import type { UploadRequestOptions } from 'element-plus'
import StatusTag from '@/components/StatusTag.vue'
import MrProTable, { type MrColumn, type MrQuery } from '@/components/MrProTable.vue'
import AsyncPanel from '@/components/AsyncPanel.vue'
import { useAsyncData } from '@/composables/useAsyncData'
import { hasToken } from '@/api/client'
import { apiErrorHint, notifyApiError } from '@/api/errors'
import { contractState, contractLabel } from '@/api/dataSource'
import { downloadSourceFile } from '@/api/documentFiles'
import { getDocument, getDocumentHistory, listDocuments } from '@/api/frontend'
import { uploadFile, createParseTask, UPLOAD_LIMIT_BYTES, UPLOAD_ALLOWED_EXT, MAX_FILES_PER_TASK } from '@/api/parse'
import type { DocumentInfo, DocumentList, DocumentQuery, ParseHistory, ParseTask } from '@/api/types'

const router = useRouter()
const ACCEPT = UPLOAD_ALLOWED_EXT.join(',')
const hasAuth = computed(() => hasToken())
const contractTagType = computed(() => (contractState.value === 'ready' ? 'success' : 'warning'))

/* ───────── 真实文档列表（受控 MrProTable） ───────── */
const query = ref<DocumentQuery>({ page: 1, pageSize: 20, keyword: '', status: '', docType: '' })
const list = useAsyncData<DocumentList>((signal) => listDocuments(query.value, signal), { immediate: false })

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
    docType: (String(q.search.doc_type || '') || '') as DocumentQuery['docType']
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
    const task = await createParseTask({ file_ids: [id] }, crypto.randomUUID())
    lastTask.value = task
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
interface RealUpload { fileId: string; name: string; sha256: string; bytes: number; at: string }

const uploadQueue = ref<QueueItem[]>([])
const realUploads = ref<RealUpload[]>([])
const uploadedHashes = new Set<string>()
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
      at: new Date().toLocaleString('zh-CN')
    })
    ElMessage.success(`${file.name} 上传成功，SHA256 由后端返回`)
    void list.load()
  } catch (err) {
    notifyApiError(err, '上传失败')
    fail(item, apiErrorHint(err), false)
  }
}

async function createTaskFor(row: RealUpload) {
  if (submittingId.value || !hasAuth.value) return
  submittingId.value = row.fileId
  try {
    const task = await createParseTask({ file_ids: [row.fileId] }, crypto.randomUUID())
    lastTask.value = task
    ElMessage.success(`解析任务已创建：${task.task_id}`)
    void list.load()
  } catch (err) {
    notifyApiError(err, '创建解析任务失败')
  } finally {
    submittingId.value = ''
  }
}
</script>

<style scoped>
.header-tags { display: flex; gap: 8px; align-items: center; }
.contract-note { margin-bottom: 12px; }
.upload-card :deep(.el-upload-dragger) { padding: 24px; }
.card-head { display: flex; justify-content: space-between; align-items: center; font-weight: 600; }
.card-sub { font-weight: 400; font-size: 12px; color: var(--mr-text-3); }
.upload-queue { margin-top: 16px; border-top: 1px dashed var(--mr-line); padding-top: 12px; }
.queue-summary { font-size: 13px; color: var(--mr-text-2); margin-bottom: 8px; display: flex; align-items: center; gap: 12px; }
.queue-item { display: flex; align-items: center; gap: 12px; margin: 6px 0; flex-wrap: wrap; }
.queue-name { width: 240px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 13px; }
.queue-size { width: 80px; text-align: right; color: var(--mr-text-3); font-size: 12px; }
.queue-msg { flex-basis: 100%; font-size: 12px; color: var(--mr-st-danger); }
.sha { font-size: 12px; word-break: break-all; color: var(--mr-text-2); }
.drawer-pager { margin-top: 10px; display: flex; justify-content: flex-end; }
</style>
