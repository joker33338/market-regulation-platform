<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h1 class="page-title">智能解析中心</h1>
        <p class="page-desc">OCR 双引擎 + MinerU 云端回退的任务调度与追踪（引擎与状态全部以后端返回为准）</p>
      </div>
      <div class="header-tags">
        <el-tag type="success" effect="plain">真实接口 /api/parse/tasks</el-tag>
        <el-tag :type="contractState === 'ready' ? 'success' : 'warning'" effect="plain">{{ contractLabel[contractState] }}</el-tag>
      </div>
    </div>

    <!-- 后端真实配置：GET /api/parse/info，不伪造引擎在线状态 -->
    <el-card shadow="never" class="info-card">
      <div class="info-row">
        <span class="info-label">后端真实配置 <span class="real-badge">REAL</span></span>
        <template v-if="store.serviceInfo">
          <el-tag v-for="c in backendConfig" :key="c" size="small" effect="plain">{{ c }}</el-tag>
        </template>
        <span v-else class="mr-disabled-hint">未探测到 /api/parse/info（未配置 Token、接口不可用或服务离线）</span>
        <el-button size="small" style="margin-left: auto" @click="store.probeBackend()">重新探测</el-button>
      </div>
    </el-card>

    <!-- 解析路由策略：仅展示后端决策链路，前端不指定引擎 -->
    <el-card shadow="never" style="margin-top: 16px">
      <template #header>
        <div class="card-head-title">
          <span>解析路由策略（由 FastAPI 后端决定）</span>
          <span class="card-sub">selected_engine / fallback_reason / requires_review / quality.routing_trace 全部取自后端</span>
        </div>
      </template>
      <div class="route-flow">
        <div class="route-node"><div class="route-node-title">本地解析</div><div class="route-node-desc">PaddleOCR / PP-StructureV3</div></div>
        <div class="route-arrow">→</div>
        <div class="route-node"><div class="route-node-title">质量评估</div><div class="route-node-desc">后端质量门禁判定</div></div>
        <div class="route-arrow">→</div>
        <div class="route-node route-node-warn"><div class="route-node-title">MinerU 回退</div><div class="route-node-desc">仅后端判定需要时</div></div>
        <div class="route-arrow">→</div>
        <div class="route-node route-node-ok"><div class="route-node-title">结果标准化</div><div class="route-node-desc">统一结构 + 来源标记</div></div>
      </div>
      <div class="mr-disabled-hint" style="margin-top: 10px">
        前端不按文件类型判断引擎、不模拟回退成功；结构化阶段日志接口 <code>GET /api/parse/tasks/{id}/logs</code> 后端未实现，日志抽屉只展示 public(task) 真实字段。
      </div>
    </el-card>

    <!-- 三引擎面板：状态来自 /api/system/health（仅文件/配置检查），统计由当前页真实任务聚合 -->
    <div class="card-grid" style="grid-template-columns: repeat(3, 1fr); margin-top: 16px">
      <el-card v-for="p in enginePanels" :key="p.key" shadow="never" class="engine-card">
        <div class="engine-head">
          <span class="engine-name">{{ p.name }}</span>
          <span class="engine-state">
            <span class="status-dot" :style="{ background: stateColor(p.state) }" />
            <b :class="`mr-state-${p.state}`">{{ p.state }}</b>
          </span>
        </div>
        <div class="engine-cap">{{ p.capability }}</div>
        <div class="engine-metrics">
          <div><span class="num">{{ p.taskCount }}</span><label>本页任务</label></div>
          <div><span class="num" style="color: var(--mr-st-success)">{{ p.successCount }}</span><label>成功</label></div>
          <div><span class="num" style="color: var(--mr-st-danger)">{{ p.failedCount }}</span><label>失败</label></div>
          <div><span class="num">{{ p.avgSeconds == null ? '—' : p.avgSeconds + 's' }}</span><label>平均耗时</label></div>
        </div>
        <div class="engine-note">{{ p.note }}</div>
      </el-card>
    </div>

    <!-- 创建解析任务：真实接口 POST /api/parse/tasks -->
    <el-card shadow="never" style="margin-top: 16px">
      <template #header>
        <div class="card-head-title">
          <span>创建解析任务 <span class="real-badge">REAL</span></span>
          <span class="card-sub">POST /api/parse/tasks · 必带 Idempotency-Key · 幂等防重复提交</span>
        </div>
      </template>
      <div class="create-row">
        <el-input v-model="fileIdsInput" type="textarea" :rows="2"
          placeholder="粘贴上传接口返回的 file_id（32 位十六进制，多个用逗号或换行分隔，1–20 个）" />
        <el-button type="primary" :loading="submitting" :disabled="!canCreate" @click="submitTask">创建任务</el-button>
      </div>
      <div class="mr-disabled-hint" style="margin-top: 8px">
        <template v-if="!hasAuth">未配置 API Token，请在系统监控页配置。</template>
        <template v-else-if="!fileIdsValid">请填写 1–20 个合法的 32 位十六进制 file_id（当前 {{ parsedFileIds.length }} 个）。</template>
        <template v-else>请求体仅含 file_ids，引擎选择、质量评估与 MinerU 回退全部由后端决定；页面刷新只查询任务，不会重新创建。</template>
      </div>
      <el-alert v-if="lastCreated" type="success" :closable="false" style="margin-top: 12px"
        :title="`任务已由后端创建：${lastCreated.task_id}（状态 ${lastCreated.status}）`" />
    </el-card>

    <!-- 任务列表：真实 GET /api/parse/tasks -->
    <el-card shadow="never" style="margin-top: 16px">
      <template #header>
        <div class="card-head-title task-head">
          <span>解析任务列表 <span class="real-badge">REAL</span></span>
          <div class="task-tools">
            <el-tag v-if="polling" size="small" type="primary" effect="plain">轮询中 2s</el-tag>
            <el-button v-if="polling" size="small" @click="stopPolling">停止轮询</el-button>
            <el-input v-model="realTaskId" placeholder="按任务 ID 查询后端（GET /api/parse/tasks/{id}）" clearable style="width: 300px" @keyup.enter="queryRealTask">
              <template #append><el-button @click="queryRealTask">查询</el-button></template>
            </el-input>
            <el-button size="small" @click="list.load()">刷新</el-button>
          </div>
        </div>
      </template>
      <div class="mr-disabled-hint" style="margin-bottom: 10px">
        列表参数仅 page / page_size / status / engine（契约限定）。后端未提供总工作量时<b>不展示模拟进度百分比</b>；耗时仅显示后端 elapsed_seconds。
      </div>
      <MrProTable
        :columns="columns"
        :rows="tableRows"
        :total="list.data.value?.total || 0"
        :loading="list.loading.value"
        :state="list.state.value"
        :error="list.error.value"
        @query="onQuery"
        @retry="list.load()"
      >
        <template #col-status="{ row }"><StatusTag :status="String(row.status)" /></template>
        <template #col-review="{ row }">
          <el-tag v-if="row.requiresReview" size="small" type="warning" effect="plain">需人工复核</el-tag>
          <span v-else>—</span>
        </template>
        <template #extra-columns>
          <el-table-column label="操作" width="250" fixed="right">
            <template #default="{ row }">
              <el-button text size="small" type="primary" @click="queryRealTaskById(String(row.taskId))">详情</el-button>
              <el-button text size="small" @click="viewLogs(String(row.taskId))">日志</el-button>
              <el-button text size="small" @click="gotoPreview(String(row.taskId), String(row.firstFileId))">Chunk 预览</el-button>
              <el-button text size="small" :disabled="isTerminalStatus(String(row.status))" @click="retryById(String(row.taskId))">重试</el-button>
            </template>
          </el-table-column>
        </template>
        <template #empty>
          <el-empty :image-size="70" description="当前筛选条件下没有解析任务（后端返回空列表）">
            <el-button size="small" @click="list.load()">刷新</el-button>
          </el-empty>
        </template>
      </MrProTable>
    </el-card>

    <!-- 任务详情抽屉 -->
    <el-drawer v-model="drawer" title="任务详情（后端真实返回）" size="680px" @closed="stopPolling">
      <AsyncPanel :state="detailState" :error="detailError" empty-text="请先按任务 ID 查询后端" @retry="queryRealTask">
        <template v-if="realDetail">
          <el-alert type="success" :closable="false" style="margin-bottom: 14px"
            :title="`后端 public(task) · 状态 ${realDetail.status}${polling ? ' · 轮询中' : ''}`" />
          <el-alert v-if="pollError" type="warning" :closable="false" style="margin-bottom: 12px"
            :title="`轮询已停止：${pollError}`">
            <template #default><el-button size="small" @click="resumePolling">重试轮询</el-button></template>
          </el-alert>

          <el-descriptions :column="2" border>
            <el-descriptions-item label="任务 ID" :span="2"><code class="mono">{{ realDetail.task_id }}</code></el-descriptions-item>
            <el-descriptions-item label="provider">{{ realDetail.provider }}</el-descriptions-item>
            <el-descriptions-item label="mode">{{ realDetail.mode }}</el-descriptions-item>
            <el-descriptions-item label="状态"><StatusTag :status="realDetail.status" /></el-descriptions-item>
            <el-descriptions-item label="取消请求">{{ realDetail.cancel_requested ? '是' : '否' }}</el-descriptions-item>
            <el-descriptions-item label="开始时间">{{ formatTime(realDetail.created_at) }}</el-descriptions-item>
            <el-descriptions-item label="完成时间">{{ realDetail.completed_at ? formatTime(realDetail.completed_at) : '—' }}</el-descriptions-item>
            <el-descriptions-item label="错误" :span="2">{{ formatError(realDetail.error) }}</el-descriptions-item>
          </el-descriptions>

          <el-divider content-position="left">任务文件（引擎与回退均由后端返回）</el-divider>
          <el-table :data="realDetail.files" size="small">
            <el-table-column prop="file_name" label="文件" min-width="150" show-overflow-tooltip />
            <el-table-column label="选定引擎" width="150"><template #default="{ row }">{{ engineLabel(row.selected_engine) }}</template></el-table-column>
            <el-table-column label="状态" width="100"><template #default="{ row }"><StatusTag :status="row.status" /></template></el-table-column>
            <el-table-column label="需复核" width="80"><template #default="{ row }">{{ row.requires_review ? '是' : '否' }}</template></el-table-column>
            <el-table-column label="回退原因" min-width="150" show-overflow-tooltip><template #default="{ row }">{{ row.fallback_reason || '—' }}</template></el-table-column>
            <el-table-column label="错误" min-width="140" show-overflow-tooltip><template #default="{ row }">{{ formatError(row.error) }}</template></el-table-column>
          </el-table>

          <el-divider content-position="left">结果与操作（全部真实接口）</el-divider>
          <div class="action-row">
            <el-button size="small" @click="loadResults">标准化结果</el-button>
            <el-button size="small" @click="loadErrors">错误原因</el-button>
            <el-button size="small" :disabled="!realDetail.files.length" @click="downloadArtifact">下载解析产物</el-button>
            <el-button size="small" @click="retryReal">重试任务</el-button>
            <el-button size="small" :disabled="isTerminalStatus(realDetail.status)" @click="cancelReal">取消任务</el-button>
            <el-button size="small" :disabled="!realDetail.files.length" @click="gotoPreview(realDetail.task_id, realDetail.files[0].file_id)">Chunk 预览</el-button>
          </div>
          <div class="mr-disabled-hint" style="margin-top: 6px">
            artifact.bin 是 MinerU 解析产物归档，<b>不是原始证据文件</b>；原始文件请用文档管理页的授权下载。
          </div>
          <pre v-if="resultJson" class="result-json">{{ resultJson }}</pre>
        </template>
      </AsyncPanel>
    </el-drawer>

    <el-drawer v-model="logDrawer" title="解析日志" size="560px">
      <el-alert type="info" :closable="false" style="margin-bottom: 12px"
        title="结构化阶段日志接口未接入"
        description="后端未提供 GET /api/parse/tasks/{id}/logs。以下内容仅由 public(task) 真实字段生成，不含任何虚构的阶段事件、耗时或成功记录。" />
      <pre class="result-json">{{ logContent }}</pre>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import StatusTag from '@/components/StatusTag.vue'
import MrProTable, { type MrColumn, type MrQuery } from '@/components/MrProTable.vue'
import AsyncPanel from '@/components/AsyncPanel.vue'
import { useAsyncData } from '@/composables/useAsyncData'
import { useAppStore } from '@/stores/app'
import { hasToken } from '@/api/client'
import { toApiError, notifyApiError } from '@/api/errors'
import { contractState, contractLabel } from '@/api/dataSource'
import { listParseTasks, getSystemHealth } from '@/api/frontend'
import {
  getParseTask, getParseTaskErrors, getParseTaskResults, getFileArtifact,
  resumeParseTask, cancelParseTask, createParseTask
} from '@/api/parse'
import {
  isTerminalStatus, type ComponentState, type HealthResponse,
  type ParseTask, type TaskList, type TaskQuery
} from '@/api/types'
import type { LoadState } from '@/api/types'

const route = useRoute()
const router = useRouter()
const store = useAppStore()
const hasAuth = computed(() => hasToken())

/* ───────── 真实任务列表 ───────── */
const query = ref<TaskQuery>({ page: 1, pageSize: 20, status: '', engine: '' })
const list = useAsyncData<TaskList>((signal) => listParseTasks(query.value, signal), { immediate: false })

const columns: MrColumn[] = [
  { prop: 'taskId', label: '任务 ID', width: 160, showOverflowTooltip: true },
  { prop: 'fileName', label: '文档名称', minWidth: 200, showOverflowTooltip: true },
  { prop: 'engine', label: '使用引擎（后端）', width: 160, search: { el: 'input', placeholder: 'engine 筛选' } },
  { prop: 'status', label: '任务状态', width: 120, search: { el: 'select', placeholder: 'status 筛选', options: [
    { label: '等待中', value: 'pending' }, { label: '执行中', value: 'running' },
    { label: '已完成', value: 'completed' }, { label: '部分成功', value: 'partial' },
    { label: '失败', value: 'failed' }, { label: '已取消', value: 'canceled' }, { label: '超时', value: 'timed_out' }
  ] } },
  { prop: 'startedAt', label: '开始时间', width: 155 },
  { prop: 'finishedAt', label: '完成时间', width: 155 },
  { prop: 'elapsed', label: '实际耗时', width: 100, align: 'right' },
  { prop: 'review', label: '人工复核', width: 110 }
]

const tableRows = computed<Record<string, unknown>[]>(() =>
  (list.data.value?.list || []).map((t) => ({
    taskId: t.task_id,
    fileName: t.files?.map((f) => f.file_name).filter(Boolean).join('、') || '—',
    engine: enginesOf(t),
    status: t.status,
    startedAt: formatTime(t.created_at),
    finishedAt: t.completed_at ? formatTime(t.completed_at) : '—',
    elapsed: t.elapsed_seconds == null ? '—' : `${t.elapsed_seconds}s`,
    requiresReview: !!t.files?.some((f) => f.requires_review),
    firstFileId: t.files?.[0]?.file_id || ''
  }))
)

function onQuery(q: MrQuery) {
  query.value = {
    page: q.page, pageSize: q.pageSize,
    status: String(q.search.status || ''),
    engine: String(q.search.engine || '')
  }
  void list.load()
}

function enginesOf(t: ParseTask): string {
  const set = new Set<string>()
  for (const f of t.files || []) {
    const e = f.selected_engine
    if (Array.isArray(e)) e.forEach((x) => set.add(String(x)))
    else if (e) set.add(String(e))
  }
  return set.size ? [...set].join('、') : '未记录'
}

function engineLabel(v: unknown): string {
  if (Array.isArray(v)) return v.join('、')
  return v ? String(v) : '后端未记录'
}

/* ───────── 引擎面板：状态来自 health，统计由当前页真实任务聚合 ───────── */
const health = useAsyncData<HealthResponse>((signal) => getSystemHealth(signal))
const ENGINE_KEYS = [
  { key: 'paddle_ocr', name: 'PaddleOCR', match: ['paddle', 'paddleocr'], capability: '本地 OCR · 简单文档优先' },
  { key: 'pp_structure', name: 'PP-StructureV3', match: ['ppstructure', 'pp_structure', 'structure'], capability: '本地表格 / 复杂版面识别' },
  { key: 'mineru', name: 'MinerU 云端回退', match: ['mineru'], capability: '复杂扫描件 · 仅由 FastAPI 后端调用' }
] as const

const enginePanels = computed(() => ENGINE_KEYS.map((def) => {
  const component = health.data.value?.components?.[def.key]
  const state = (component?.state || 'UNKNOWN') as ComponentState
  const rows = (list.data.value?.list || []).filter((t) =>
    (t.files || []).some((f) => {
      const e = f.selected_engine
      const names = Array.isArray(e) ? e.map(String) : e ? [String(e)] : []
      return names.some((n) => def.match.some((m) => n.toLowerCase().includes(m)))
    })
  )
  const successCount = rows.filter((t) => t.status === 'completed').length
  const failedCount = rows.filter((t) => t.status === 'failed' || t.status === 'timed_out' || t.status === 'partial').length
  const durations = rows.map((t) => t.elapsed_seconds).filter((v): v is number => typeof v === 'number')
  const avgSeconds = durations.length ? Math.round(durations.reduce((a, b) => a + b, 0) / durations.length) : null
  return {
    ...def, state, taskCount: rows.length, successCount, failedCount, avgSeconds,
    note: component?.check
      ? `后端检查方式：${component.check}${component.model_ready === false ? ' · 模型文件检查未通过' : ''}；不代表推理或云 API 在线`
      : '健康检查未返回该组件（未配置 / 服务不可达）'
  }
}))

const STATE_COLOR: Record<string, string> = {
  ONLINE: 'var(--mr-state-online)', OFFLINE: 'var(--mr-state-offline)',
  NOT_CONFIGURED: 'var(--mr-state-not-configured)', UNKNOWN: 'var(--mr-state-unknown)', ERROR: 'var(--mr-state-error)'
}
function stateColor(s: string) { return STATE_COLOR[s] || STATE_COLOR.UNKNOWN }

/* ───────── 创建任务（幂等键防重复提交） ───────── */
const fileIdsInput = ref('')
const submitting = ref(false)
const lastCreated = ref<ParseTask | null>(null)
const parsedFileIds = computed(() => fileIdsInput.value.split(/[\s,]+/).map((s) => s.trim()).filter(Boolean))
const fileIdsValid = computed(() => parsedFileIds.value.length > 0 && parsedFileIds.value.length <= 20 && parsedFileIds.value.every((id) => /^[0-9a-fA-F]{32}$/.test(id)))
const canCreate = computed(() => hasAuth.value && fileIdsValid.value && !submitting.value)

async function submitTask() {
  if (!canCreate.value || submitting.value) return
  submitting.value = true
  try {
    const task = await createParseTask({ file_ids: parsedFileIds.value }, crypto.randomUUID())
    lastCreated.value = task
    realTaskId.value = task.task_id
    ElMessage.success(`解析任务已创建：${task.task_id}`)
    void list.load()
    await queryRealTask()
  } catch (err) {
    notifyApiError(err, '创建解析任务失败')
  } finally {
    submitting.value = false
  }
}

/* ───────── 按真实任务 ID 查询 + 可停止轮询 ───────── */
const realTaskId = ref('')
const realDetail = ref<ParseTask | null>(null)
const detailState = ref<LoadState>('empty')
const detailError = ref('')
const resultJson = ref('')
const drawer = ref(false)
const polling = ref(false)
const pollError = ref('')
let pollTimer: number | null = null
let pollController: AbortController | null = null
let pollTicks = 0

const backendConfig = computed(() => {
  const i = store.serviceInfo
  if (!i) return []
  return [
    `provider: ${i.provider}`, `mode: ${i.mode}`, `enabled: ${i.enabled}`,
    `dual_engine_enabled: ${i.dual_engine_enabled}`, `database_enabled: ${i.database_enabled}`
  ]
})

function stopPolling() {
  if (pollTimer !== null) { clearInterval(pollTimer); pollTimer = null }
  if (pollController) { pollController.abort(); pollController = null }
  polling.value = false
}

async function pollTick(taskId: string) {
  pollTicks++
  const ctrl = new AbortController()
  pollController = ctrl
  try {
    const t = await getParseTask(taskId, ctrl.signal)
    if (ctrl.signal.aborted) return
    realDetail.value = t
    detailState.value = 'ready'
    pollError.value = ''
    if (isTerminalStatus(t.status) || pollTicks >= 150) stopPolling()
  } catch (err) {
    if (ctrl.signal.aborted) return
    stopPolling()
    pollError.value = toApiError(err).hint
  } finally {
    if (pollController === ctrl) pollController = null
  }
}

function startPolling(taskId: string) {
  stopPolling()
  if (isTerminalStatus(realDetail.value?.status || '')) return
  polling.value = true
  pollTicks = 0
  pollError.value = ''
  void pollTick(taskId)
  if (polling.value && pollTimer === null) pollTimer = window.setInterval(() => void pollTick(taskId), 2000)
}

function resumePolling() {
  const id = realDetail.value?.task_id || realTaskId.value.trim()
  if (id) startPolling(id)
}

async function queryRealTask() {
  const id = realTaskId.value.trim()
  if (!id) return
  if (!hasAuth.value) {
    ElMessage.warning('请先在系统监控页配置 API Token')
    return
  }
  stopPolling()
  detailState.value = 'loading'
  detailError.value = ''
  resultJson.value = ''
  drawer.value = true
  const ctrl = new AbortController()
  pollController = ctrl
  try {
    // 旧接口 GET /api/parse/tasks/{id}：不依赖新契约，服务未切换时仍可查询真实任务
    const task = await getParseTask(id, ctrl.signal)
    if (ctrl.signal.aborted) return
    realDetail.value = task
    detailState.value = 'ready'
    startPolling(id)
  } catch (err) {
    if (ctrl.signal.aborted) return
    const e = toApiError(err)
    detailError.value = e.hint
    detailState.value = e.kind === 'no-permission' ? 'no-permission'
      : e.kind === 'unavailable' ? 'unavailable' : e.kind === 'not-found' ? 'empty' : 'error'
  } finally {
    if (pollController === ctrl) pollController = null
  }
}

function queryRealTaskById(id: string) {
  realTaskId.value = id
  void queryRealTask()
}

/* ───────── 结果与操作 ───────── */
async function loadResults() {
  if (!realDetail.value) return
  try { resultJson.value = JSON.stringify(await getParseTaskResults(realDetail.value.task_id), null, 2) }
  catch (err) { notifyApiError(err, '获取标准化结果失败') }
}
async function loadErrors() {
  if (!realDetail.value) return
  try { resultJson.value = JSON.stringify(await getParseTaskErrors(realDetail.value.task_id), null, 2) }
  catch (err) { notifyApiError(err, '获取错误原因失败') }
}
async function downloadArtifact() {
  if (!realDetail.value?.files.length) return
  const taskId = realDetail.value.task_id
  const fileId = realDetail.value.files[0].file_id
  try {
    const buf = await getFileArtifact(taskId, fileId)
    const url = URL.createObjectURL(new Blob([buf], { type: 'application/octet-stream' }))
    const a = document.createElement('a')
    a.href = url
    a.download = `${taskId}-${fileId}-artifact.bin`
    a.click()
    window.setTimeout(() => URL.revokeObjectURL(url), 3000)
    ElMessage.info('已下载 artifact.bin（解析产物，非原始文件）')
  } catch (err) { notifyApiError(err, '解析产物下载失败') }
}
async function retryReal() {
  if (!realDetail.value) return
  try {
    await ElMessageBox.confirm(`确认重试任务 ${realDetail.value.task_id}？`, '重试确认', { type: 'warning' })
    realDetail.value = await resumeParseTask(realDetail.value.task_id)
    ElMessage.success('后端已返回最新任务状态')
    startPolling(realDetail.value.task_id)
    void list.load()
  } catch (err) {
    if (err !== 'cancel' && !(err instanceof Error && err.message === 'cancel')) notifyApiError(err, '重试失败')
  }
}
async function retryById(id: string) {
  if (!id) return
  try {
    await ElMessageBox.confirm(`确认重试任务 ${id}？`, '重试确认', { type: 'warning' })
    await resumeParseTask(id)
    ElMessage.success('重试请求已提交，以后端返回状态为准')
    void list.load()
  } catch (err) {
    if (err !== 'cancel' && !(err instanceof Error && err.message === 'cancel')) notifyApiError(err, '重试失败')
  }
}
async function cancelReal() {
  if (!realDetail.value) return
  try {
    await ElMessageBox.confirm(`确认取消任务 ${realDetail.value.task_id}？`, '取消确认', { type: 'warning' })
    realDetail.value = await cancelParseTask(realDetail.value.task_id)
    ElMessage.success('取消请求已提交，以后端返回状态为准')
    void list.load()
  } catch (err) {
    if (err !== 'cancel' && !(err instanceof Error && err.message === 'cancel')) notifyApiError(err, '取消失败')
  }
}

function viewLogs(taskId: string) {
  const t = realDetail.value?.task_id === taskId ? realDetail.value : null
  logContent.value = t
    ? [
        '【来源】后端 public(task) 真实字段；结构化 /logs 接口未实现',
        `task_id   : ${t.task_id}`,
        `status    : ${t.status}`,
        `provider  : ${t.provider}`,
        `mode      : ${t.mode}`,
        `created_at: ${t.created_at}`,
        `completed_at: ${t.completed_at || '—'}`,
        `error     : ${formatError(t.error)}`,
        ...t.files.map((f) => `file ${f.file_id} | ${f.file_name} | engine=${engineLabel(f.selected_engine)} | status=${f.status} | requires_review=${!!f.requires_review} | fallback=${f.fallback_reason || '—'} | error=${formatError(f.error)}`)
      ].join('\n')
    : `任务 ${taskId} 尚未查询后端详情。请点击该行「详情」后查看真实字段；本页不生成虚构阶段日志。`
  logDrawer.value = true
}

function gotoPreview(taskId: string, fileId: string) {
  if (!taskId || !fileId) { ElMessage.info('该任务没有可用于预览的任务文件 ID'); return }
  void router.push({ path: '/knowledge/ingestion', query: { task: taskId, file: fileId } })
}

const logDrawer = ref(false)
const logContent = ref('')

function formatTime(v: string) { return v ? v.replace('T', ' ').slice(0, 19) : '—' }
function formatError(e: unknown): string {
  if (e == null || e === '') return '—'
  if (typeof e === 'string') return e
  if (typeof e === 'object') {
    const o = e as Record<string, unknown>
    return String(o.message || o.code || JSON.stringify(e))
  }
  return String(e)
}

onBeforeUnmount(stopPolling)
onMounted(() => {
  // 首次列表加载由 MrProTable 的 onMounted emitQuery 触发，避免刷新时重复请求
  if (store.token) void store.probeBackend()
  // 从文档管理跳转：只查询，不创建任务；页面刷新同样只查询
  const task = String(route.query.task || '')
  if (task) { realTaskId.value = task; void queryRealTask() }
})
</script>

<style scoped>
.header-tags { display: flex; gap: 8px; align-items: center; }
.card-head-title { display: flex; justify-content: space-between; align-items: center; font-weight: 600; gap: 12px; flex-wrap: wrap; }
.card-sub { font-weight: 400; font-size: 12px; color: var(--mr-text-3); }
.info-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.info-label { font-weight: 600; font-size: 13px; margin-right: 6px; }
.route-flow { display: flex; align-items: center; gap: 12px; padding: 4px 0; }
.route-node { flex: 1; border: 1px solid var(--mr-line); border-radius: var(--mr-radius); padding: 12px 16px; background: #fafbfe; }
.route-node-warn { border-color: #fde68a; background: #fffbeb; }
.route-node-ok { border-color: #bbf7d0; background: #f0fdf4; }
.route-node-title { font-weight: 600; margin-bottom: 4px; }
.route-node-desc { font-size: 12px; color: var(--mr-text-2); }
.route-arrow { color: var(--mr-text-3); font-size: 18px; }
.engine-card :deep(.el-card__body) { display: flex; flex-direction: column; gap: 10px; }
.engine-head { display: flex; justify-content: space-between; align-items: center; }
.engine-name { font-weight: 700; font-size: 15px; }
.engine-state { display: inline-flex; align-items: center; font-size: 12px; color: var(--mr-text-3); gap: 4px; }
.engine-cap { font-size: 12px; color: var(--mr-text-2); }
.engine-metrics { display: grid; grid-template-columns: repeat(4, 1fr); border-top: 1px solid var(--mr-line); padding-top: 10px; }
.engine-metrics > div { display: flex; flex-direction: column; align-items: center; gap: 2px; }
.engine-metrics .num { font-size: 18px; font-weight: 700; }
.engine-metrics label { font-size: 12px; color: var(--mr-text-3); }
.engine-note { font-size: 11px; color: var(--mr-text-3); line-height: 1.6; }
.create-row { display: flex; gap: 12px; align-items: flex-start; }
.create-row :deep(.el-textarea) { flex: 1; }
.task-tools { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.action-row { display: flex; gap: 8px; flex-wrap: wrap; }
.result-json { background: #0f2b52; color: #d6e4f7; padding: 14px; border-radius: 6px; font-size: 12px; line-height: 1.6; max-height: 360px; overflow: auto; white-space: pre-wrap; word-break: break-all; }
.mono { font-family: monospace; font-size: 12px; }
@media (max-width: 1366px) {
  .route-flow { flex-wrap: wrap; }
  .route-node { min-width: 200px; }
}
</style>
