<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h1 class="page-title">文档管理</h1>
        <p class="page-desc">法规原始文件上传与全生命周期管理（原始证据文件只读，前端不可修改）</p>
      </div>
      <div style="display: flex; gap: 8px; align-items: center">
        <el-tag type="success" effect="plain">上传走真实接口</el-tag>
        <DemoBadge />
      </div>
    </div>

    <!-- 上传区：POST /api/parse/files，body 为原始二进制流 -->
    <el-card shadow="never" class="upload-card">
      <el-upload
        drag
        multiple
        :show-file-list="false"
        :http-request="doUpload"
        :accept="ACCEPT"
      >
        <el-icon size="40" color="var(--mr-primary)"><UploadFilled /></el-icon>
        <div class="el-upload__text">将文件拖到此处，或 <em>点击上传</em></div>
        <div class="el-upload__tip">
          支持 PDF / Word(.docx) / 图片(.png/.jpg/.jpeg)；单文件 ≤100MB；单次最多 20 个。
          文件头魔数预校验，SHA256 以<b>后端返回</b>为准；未配置 Token 或后端离线时不会假装上传成功。
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

    <!-- 本次会话真实上传：SHA256 / file_id 全部来自后端，标 REAL -->
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
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button text size="small" type="primary" :loading="submitting" :disabled="!hasAuth || submitting" @click="createTaskFor(row)">
              创建解析任务
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-alert v-if="lastTask" type="success" :closable="false" style="margin-top: 12px"
        :title="`解析任务已创建：${lastTask.task_id}（状态 ${lastTask.status}）— 可到智能解析中心按 ID 查询进度`" />
      <div v-if="!hasAuth" class="mr-disabled-hint" style="margin-top: 8px">
        未配置 API Token：请在系统监控页配置后，方可创建解析任务（真实接口）。
      </div>
    </el-card>

    <!-- 文档列表：MrProTable（columns 配置 → 搜索 / 表格 / 分页） -->
    <el-card shadow="never" style="margin-top: 16px">
      <template #header>
        <div class="card-head">
          <span>文档列表 <DemoBadge /></span>
          <span class="card-sub">列表 / 搜索 / 筛选 / 分页接口未接入，当前为 DEMO</span>
        </div>
      </template>
      <MrProTable ref="tableRef" :columns="columns" :fetcher="fetcher">
        <template #col-size="{ row }"><span class="num">{{ formatSize(Number(row.size)) }}</span></template>
        <template #col-status="{ row }"><StatusTag :status="String(row.status)" /></template>
        <template #extra-columns>
          <el-table-column label="操作" width="200" fixed="right">
            <template #default="{ row }">
              <el-button text size="small" type="primary" @click="openDetail(row)">详情</el-button>
              <el-tooltip :content="downloadHint" placement="top">
                <span><el-button text size="small" disabled>下载</el-button></span>
              </el-tooltip>
              <el-tooltip content="列表为 DEMO 数据，缺少真实 file_id；请通过上方真实上传创建解析任务" placement="top">
                <span><el-button text size="small" disabled>重新解析</el-button></span>
              </el-tooltip>
            </template>
          </el-table-column>
        </template>
        <template #empty>暂无符合条件的文档，调整筛选条件或上传新文件（DEMO 列表）</template>
      </MrProTable>
    </el-card>

    <!-- 详情抽屉 -->
    <el-drawer v-model="drawer" title="文件详情" size="520px">
      <template v-if="current">
        <el-alert type="warning" :closable="false" style="margin-bottom: 14px"
          title="本条为 DEMO 数据" description="SHA256 为演示示例值，非真实文件摘要；真实文件请在「本次会话真实上传」中查看后端返回值。" />
        <el-descriptions :column="1" border>
          <el-descriptions-item label="文件名称">{{ current.name }}</el-descriptions-item>
          <el-descriptions-item label="文档类型">{{ current.docType }}</el-descriptions-item>
          <el-descriptions-item label="文件格式">{{ current.fileType }}</el-descriptions-item>
          <el-descriptions-item label="文件大小">{{ formatSize(Number(current.size)) }}</el-descriptions-item>
          <el-descriptions-item label="上传时间">{{ current.uploadedAt }}</el-descriptions-item>
          <el-descriptions-item label="状态"><StatusTag :status="String(current.status)" /></el-descriptions-item>
          <el-descriptions-item label="解析引擎">{{ current.engine || '—' }}</el-descriptions-item>
          <el-descriptions-item label="页数">{{ current.pages ?? '—' }}</el-descriptions-item>
          <el-descriptions-item label="SHA256（DEMO）">
            <code class="sha">{{ current.sha256 }}</code>
            <el-button text size="small" type="primary" @click="copySha">复制</el-button>
          </el-descriptions-item>
        </el-descriptions>
        <el-divider content-position="left">解析历史</el-divider>
        <el-alert type="info" :closable="false"
          title="文档列表 / 解析历史接口未接入"
          description="当前无法查询该文档的解析历史。真实上传的文件可创建解析任务，并在智能解析中心按任务 ID 查询真实状态。" />
        <el-alert type="info" :closable="false" style="margin-top: 14px"
          title="原始文件为执法证据，平台不提供前端修改入口；解析结果与原始文件通过 SHA256 绑定。" />
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import type { UploadRequestOptions } from 'element-plus'
import StatusTag from '@/components/StatusTag.vue'
import DemoBadge from '@/components/DemoBadge.vue'
import MrProTable from '@/components/MrProTable.vue'
import { useAppStore } from '@/stores/app'
import { uploadFile, createParseTask, UPLOAD_LIMIT_BYTES, UPLOAD_ALLOWED_EXT, MAX_FILES_PER_TASK } from '@/api/parse'
import { hasToken } from '@/api/client'
import { unimplementedHint } from '@/api/dataSource'
import { SOURCE_FILE_API } from '@/api/documentFiles'
import { fetchDocuments, type DocumentItem } from '@/api/mock/documents'
import type { ParseTask } from '@/api/types'

const store = useAppStore()
const ACCEPT = UPLOAD_ALLOWED_EXT.join(',')
const downloadHint = unimplementedHint(SOURCE_FILE_API)

const docTypes = ['法律法规', '部门规章', '规范性文件', '执法指南', '标准规范']
const hasAuth = computed(() => hasToken())

interface QueueItem {
  uid: string
  name: string
  size: number
  percent: number
  error: boolean
  message?: string
}
interface RealUpload {
  fileId: string
  name: string
  sha256: string
  bytes: number
  at: string
}

const uploadQueue = ref<QueueItem[]>([])
const realUploads = ref<RealUpload[]>([])
const uploadedHashes = new Set<string>()
const submitting = ref(false)
const lastTask = ref<ParseTask | null>(null)

const uploadDone = computed(() => uploadQueue.value.filter((i) => i.percent >= 100 || i.error).length)
const totalQueueSize = computed(() => uploadQueue.value.reduce((s, i) => s + i.size, 0))

const columns = [
  { prop: 'name', label: '文件名称', minWidth: 260, sortable: true, showOverflowTooltip: true, search: { el: 'input' as const, placeholder: '搜索文件名称' } },
  { prop: 'docType', label: '文档类型', width: 110, search: { el: 'select' as const, options: docTypes.map((t) => ({ label: t, value: t })) } },
  { prop: 'status', label: '解析状态', width: 110, search: { el: 'select' as const, options: [
    { label: '待解析', value: 'pending' }, { label: '解析中', value: 'parsing' },
    { label: '解析成功', value: 'success' }, { label: '解析失败', value: 'failed' },
    { label: '待审核', value: 'reviewing' }, { label: '已审核', value: 'reviewed' },
    { label: '已入库', value: 'ingested' }
  ] } },
  { prop: 'uploadedAt', label: '上传时间', width: 150, sortable: true, search: { el: 'dateRange' as const } },
  { prop: 'size', label: '大小', width: 100, align: 'right' as const, sortable: true }
]

/** MrProTable 契约：{ page, pageSize, ...搜索项 } → { list, total } */
async function fetcher(p: Record<string, unknown>) {
  const range = Array.isArray(p.uploadedAt) ? (p.uploadedAt as [string, string]) : null
  const res = await fetchDocuments({
    keyword: String(p.name || ''),
    docType: String(p.docType || ''),
    status: String(p.status || ''),
    dateRange: range,
    page: Number(p.page) || 1,
    pageSize: Number(p.pageSize) || 10
  })
  let list = [...res.data.list] as unknown as Array<Record<string, unknown>>
  const sortBy = String(p.sortBy || '')
  const order = String(p.order || '')
  if (sortBy && order) {
    list.sort((a, b) => {
      const x = a[sortBy]
      const y = b[sortBy]
      const r = typeof x === 'number' && typeof y === 'number' ? x - y : String(x ?? '').localeCompare(String(y ?? ''))
      return order === 'asc' ? r : -r
    })
  }
  return { list, total: res.data.total }
}

function formatSize(bytes: number): string {
  if (!Number.isFinite(bytes)) return '—'
  if (bytes >= 1048576) return (bytes / 1048576).toFixed(1) + ' MB'
  if (bytes >= 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return bytes + ' B'
}

function extOf(name: string): string {
  const i = name.lastIndexOf('.')
  return i < 0 ? '' : name.slice(i).toLowerCase()
}

/** 前端文件头魔数预校验（后端仍会二次校验，前端只用于更早给出可读提示） */
async function magicOk(file: File): Promise<boolean> {
  const ext = extOf(file.name)
  const b = new Uint8Array(await file.slice(0, 8).arrayBuffer())
  const starts = (arr: number[]) => arr.every((v, i) => b[i] === v)
  if (ext === '.pdf') return starts([0x25, 0x50, 0x44, 0x46]) // %PDF
  if (ext === '.png') return starts([0x89, 0x50, 0x4e, 0x47]) // PNG
  if (ext === '.jpg' || ext === '.jpeg') return starts([0xff, 0xd8, 0xff])
  if (ext === '.docx') return starts([0x50, 0x4b, 0x03, 0x04]) // PK zip
  return false
}

/** 仅用于重复文件识别提示，不作为 SHA256 展示来源 */
async function localSha256(file: File): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', await file.arrayBuffer())
  return Array.from(new Uint8Array(digest)).map((x) => x.toString(16).padStart(2, '0')).join('')
}

function fail(item: QueueItem, message: string) {
  item.error = true
  item.message = message
  ElMessage.warning(message)
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
    fail(item, `不支持的格式 ${extOf(file.name) || '(无扩展名)'}，仅支持 PDF / DOCX / PNG / JPG / JPEG`)
    return
  }
  if (file.size > UPLOAD_LIMIT_BYTES) {
    fail(item, `文件超过 100MB 上限（${formatSize(file.size)}）`)
    return
  }
  if (!(await magicOk(file))) {
    fail(item, '文件头与扩展名不符，可能被重命名或损坏；后端会拒绝该请求')
    return
  }
  if (!hasToken()) {
    fail(item, '未配置 API Token，请在系统监控页配置后再上传')
    return
  }

  let localHash = ''
  try {
    localHash = await localSha256(file)
  } catch {
    /* 浏览器不支持 WebCrypto 时跳过重复识别，不影响上传 */
  }
  if (localHash && uploadedHashes.has(localHash)) {
    fail(item, '检测到重复文件（SHA256 与本次会话已上传文件相同），已跳过')
    return
  }

  try {
    // body 为 File 原始二进制流，不是 multipart/form-data
    const res = await uploadFile(file, (p) => { item.percent = p })
    item.percent = 100
    if (localHash) uploadedHashes.add(localHash)
    if (localHash && localHash !== res.sha256) {
      item.message = '提示：前端计算值与后端返回值不一致，请核对文件内容'
    }
    realUploads.value.unshift({
      fileId: res.file_id,
      name: file.name,
      sha256: res.sha256, // 一律以后端返回为准
      bytes: res.bytes,
      at: new Date().toLocaleString('zh-CN')
    })
    ElMessage.success(`${file.name} 上传成功，SHA256 由后端返回`)
  } catch {
    fail(item, '上传失败，请检查后端服务、Token 与文件格式')
  }
}

/** 真实接口 POST /api/parse/tasks：使用最小白名单请求体 + 幂等键防重复提交 */
async function createTaskFor(row: RealUpload) {
  if (submitting.value || !hasToken()) return
  submitting.value = true
  try {
    const task = await createParseTask({ file_ids: [row.fileId] }, crypto.randomUUID())
    lastTask.value = task
    ElMessage.success(`解析任务已创建：${task.task_id}`)
  } catch {
    /* 拦截器已给出可读错误 */
  } finally {
    submitting.value = false
  }
}

const drawer = ref(false)
const current = ref<DocumentItem | Record<string, unknown> | null>(null)

function openDetail(row: DocumentItem | Record<string, unknown>) {
  current.value = row
  drawer.value = true
}

function copySha() {
  const v = current.value?.sha256
  if (typeof v === 'string') {
    navigator.clipboard.writeText(v)
    ElMessage.success('SHA256 已复制')
  }
}

onMounted(() => {
  if (store.token) store.probeBackend()
})
</script>

<style scoped>
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
</style>
