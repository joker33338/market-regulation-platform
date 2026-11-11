<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h1 class="page-title">智能解析中心</h1>
        <p class="page-desc">OCR 双引擎 + MinerU 云端回退的任务调度与追踪（路由决策以后端返回为准）</p>
      </div>
      <div style="display: flex; gap: 8px; align-items: center">
        <el-tag type="success" effect="plain">任务详情走真实接口</el-tag>
        <DemoBadge />
      </div>
    </div>

    <!-- 后端真实配置：GET /api/parse/info，不伪造引擎在线状态 -->
    <el-card shadow="never" class="info-card">
      <div class="info-row">
        <span class="info-label">后端真实配置 <span class="real-badge">REAL</span></span>
        <template v-if="backendConfig">
          <el-tag v-for="c in backendConfig" :key="c" size="small" effect="plain">{{ c }}</el-tag>
        </template>
        <span v-else class="mr-disabled-hint">未探测到 /api/parse/info（未配置 Token 或后端离线）</span>
        <el-button size="small" style="margin-left: auto" @click="probe">重新探测</el-button>
      </div>
    </el-card>

    <!-- 解析路由策略：仅展示后端决策链路，前端不指定引擎 -->
    <el-card shadow="never" style="margin-top: 16px">
      <template #header>
        <div class="card-head-title" style="display: flex; justify-content: space-between; align-items: center">
          <span>解析路由策略（由 FastAPI 后端决定）</span>
          <span class="card-sub">selected_engine / fallback_reason / requires_review 全部取自 GET /api/parse/tasks/{id}</span>
        </div>
      </template>
      <div class="route-flow">
        <div class="route-node"><div class="route-node-title">本地解析</div><div class="route-node-desc">PaddleOCR / PP-StructureV3</div></div>
        <div class="route-arrow">→</div>
        <div class="route-node"><div class="route-node-title">质量评估</div><div class="route-node-desc">置信度 / 表格完整度</div></div>
        <div class="route-arrow">→</div>
        <div class="route-node route-node-warn"><div class="route-node-title">MinerU 回退</div><div class="route-node-desc">仅复杂扫描件 / 本地不达标</div></div>
        <div class="route-arrow">→</div>
        <div class="route-node route-node-ok"><div class="route-node-title">结果标准化</div><div class="route-node-desc">统一结构 + 来源标记</div></div>
      </div>
    </el-card>

    <!-- 三引擎面板：统计来自统一快照，状态无探活接口 → UNKNOWN -->
    <div class="card-grid" style="grid-template-columns: repeat(3, 1fr); margin-top: 16px">
      <el-card v-for="p in panels" :key="p.engine" shadow="never" class="engine-card">
        <div class="engine-head">
          <span class="engine-name">{{ p.engine }}</span>
          <span class="engine-state">
            <span class="status-dot" style="background: var(--mr-state-unknown)" />
            <b class="mr-state-UNKNOWN">{{ p.state }}</b><span>无探活接口</span><DemoBadge />
          </span>
        </div>
        <div class="engine-cap">{{ p.capability }}</div>
        <div class="engine-metrics">
          <div><span class="num">{{ p.taskCount }}</span><label>解析任务</label></div>
          <div><span class="num" style="color: var(--mr-st-success)">{{ p.successCount }}</span><label>成功</label></div>
          <div><span class="num" style="color: var(--mr-st-danger)">{{ p.failedCount }}</span><label>失败</label></div>
          <div><span class="num">{{ p.avgSeconds }}s</span><label>平均耗时</label></div>
        </div>
      </el-card>
    </div>

    <!-- 创建解析任务：真实接口 POST /api/parse/tasks -->
    <el-card shadow="never" style="margin-top: 16px">
      <template #header>
        <div class="card-head-title" style="display: flex; justify-content: space-between; align-items: center">
          <span>创建解析任务 <span class="real-badge">REAL</span></span>
          <span class="card-sub">POST /api/parse/tasks · 带 Idempotency-Key 防重复提交</span>
        </div>
      </template>
      <div class="create-row">
        <el-input
          v-model="fileIdsInput"
          type="textarea"
          :rows="2"
          placeholder="粘贴后端上传接口返回的 file_id（32 位十六进制，多个用逗号或换行分隔，1–20 个）"
        />
        <el-button type="primary" :loading="submitting" :disabled="!canCreate" @click="submitTask">创建任务</el-button>
      </div>
      <div class="mr-disabled-hint" style="margin-top: 8px">
        <template v-if="!hasAuth">未配置 API Token，请在系统监控页配置。</template>
        <template v-else-if="!fileIdsValid">请填写 1–20 个合法的 32 位十六进制 file_id（当前 {{ parsedFileIds.length }} 个）。</template>
        <template v-else>请求体仅含 file_ids，引擎选择、质量评估与 MinerU 回退全部由后端决定；前端不指定引擎、不模拟成功。</template>
      </div>
      <el-alert v-if="lastCreated" type="success" :closable="false" style="margin-top: 12px"
        :title="`任务已创建：${lastCreated.task_id}（状态 ${lastCreated.status}）`" />
    </el-card>

    <!-- 任务列表：DEMO 列表 + 真实 ID 查询 -->
    <el-card shadow="never" style="margin-top: 16px">
      <template #header>
        <div class="card-head-title" style="display: flex; justify-content: space-between; align-items: center">
          <span>解析任务列表 <DemoBadge /></span>
          <div style="display: flex; gap: 8px; align-items: center">
            <el-tag v-if="polling" size="small" type="primary" effect="plain">轮询中 2s</el-tag>
            <el-input v-model="realTaskId" placeholder="输入真实任务 ID 查询后端" clearable style="width: 250px" @keyup.enter="queryRealTask">
              <template #append><el-button @click="queryRealTask">查询</el-button></template>
            </el-input>
          </div>
        </div>
      </template>
      <div class="mr-disabled-hint" style="margin-bottom: 10px">
        列表为演示数据（{{ unimplementedHint('GET /api/parse/tasks') }}）；真实任务请用上方输入框按 ID 查询，状态来自后端并自动轮询。
      </div>

      <el-table :data="tasks" size="default">
        <el-table-column prop="taskId" label="任务 ID" width="160" />
        <el-table-column prop="fileName" label="文件名称" min-width="220" show-overflow-tooltip />
        <el-table-column prop="docType" label="文档类型" width="100" />
        <el-table-column prop="pages" label="页数" width="70" align="right"><template #default="{ row }"><span class="num">{{ row.pages }}</span></template></el-table-column>
        <el-table-column prop="engine" label="引擎（DEMO）" width="130" />
        <el-table-column prop="stage" label="当前阶段" width="130" show-overflow-tooltip />
        <el-table-column label="进度" width="130">
          <template #default="{ row }">
            <el-progress :percentage="row.progress" :stroke-width="8" :status="row.status === 'failed' ? 'exception' : row.status === 'completed' ? 'success' : undefined" />
          </template>
        </el-table-column>
        <el-table-column prop="startedAt" label="开始时间" width="140" />
        <el-table-column label="耗时" width="90" align="right"><template #default="{ row }"><span class="num">{{ formatElapsed(row.elapsedSeconds) }}</span></template></el-table-column>
        <el-table-column label="状态" width="100"><template #default="{ row }"><StatusTag :status="row.status" /></template></el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button text size="small" type="primary" @click="openDetail(row)">详情</el-button>
            <el-button text size="small" type="primary" @click="viewLogs(row)">日志</el-button>
            <el-tooltip content="仅真实任务可重试：请先用任务 ID 查询后端" placement="top"><span><el-button text size="small" disabled>重试</el-button></span></el-tooltip>
            <el-tooltip content="仅真实任务可取消：请先用任务 ID 查询后端" placement="top"><span><el-button text size="small" disabled>取消</el-button></span></el-tooltip>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 任务详情抽屉 -->
    <el-drawer v-model="drawer" title="任务详情" size="640px" @closed="stopPolling">
      <template v-if="detailRow">
        <el-alert v-if="!realDetail" type="warning" :closable="false" style="margin-bottom: 14px"
          title="这是 DEMO 任务" description="仅展示界面结构，不代表真实解析状态。请用任务 ID 查询后端获取真实数据。" />
        <el-alert v-else type="success" :closable="false" style="margin-bottom: 14px"
          :title="`后端真实返回 · ${realDetail.status}${polling ? ' · 轮询中' : ''}`" />

        <el-descriptions :column="2" border>
          <el-descriptions-item label="任务 ID" :span="2">{{ detailRow.taskId }}</el-descriptions-item>
          <el-descriptions-item label="文件名称" :span="2">{{ detailRow.fileName }}</el-descriptions-item>
          <el-descriptions-item label="引擎（DEMO）">{{ detailRow.engine }}</el-descriptions-item>
          <el-descriptions-item label="状态"><StatusTag :status="detailRow.status" /></el-descriptions-item>
          <el-descriptions-item v-if="detailRow.fallbackReason" label="回退原因" :span="2">
            <el-tag size="small" type="warning" effect="plain">{{ detailRow.fallbackReason }}</el-tag>
          </el-descriptions-item>
        </el-descriptions>

        <template v-if="realDetail">
          <el-divider content-position="left">后端 public(task) 真实字段</el-divider>
          <el-descriptions :column="2" border>
            <el-descriptions-item label="provider">{{ realDetail.provider }}</el-descriptions-item>
            <el-descriptions-item label="mode">{{ realDetail.mode }}</el-descriptions-item>
            <el-descriptions-item label="created_at">{{ realDetail.created_at }}</el-descriptions-item>
            <el-descriptions-item label="completed_at">{{ realDetail.completed_at || '—' }}</el-descriptions-item>
            <el-descriptions-item label="error" :span="2">{{ realDetail.error || '—' }}</el-descriptions-item>
          </el-descriptions>
          <el-table :data="realDetail.files" size="small" style="margin-top: 12px">
            <el-table-column prop="file_name" label="文件" min-width="150" show-overflow-tooltip />
            <el-table-column prop="selected_engine" label="选定引擎（后端）" width="150" />
            <el-table-column prop="status" label="状态" width="90" />
            <el-table-column label="需审核" width="80"><template #default="{ row }">{{ row.requires_review ? '是' : '否' }}</template></el-table-column>
            <el-table-column label="回退原因" min-width="180" show-overflow-tooltip>
              <template #default="{ row }">{{ row.fallback_reason || '—' }}</template>
            </el-table-column>
            <el-table-column label="错误" min-width="160" show-overflow-tooltip>
              <template #default="{ row }">{{ formatFileError(row.error) }}</template>
            </el-table-column>
          </el-table>
        </template>

        <el-divider content-position="left">结果查看（真实接口）</el-divider>
        <div style="display: flex; gap: 8px; flex-wrap: wrap">
          <el-button size="small" :disabled="!realDetail" @click="loadResults">标准化结果</el-button>
          <el-button size="small" :disabled="!realDetail" @click="loadErrors">错误原因</el-button>
          <el-button size="small" :disabled="!realDetail" @click="downloadArtifact">下载解析产物</el-button>
          <el-button size="small" :disabled="!realDetail" @click="retryReal">重试任务</el-button>
          <el-button size="small" :disabled="!realDetail" @click="cancelReal">取消任务</el-button>
        </div>
        <div class="mr-disabled-hint" style="margin-top: 6px">
          解析产物为 artifact.bin（MinerU 结果归档），<b>不是原始证据文件</b>；原始文件预览需后端 source 接口。
        </div>
        <pre v-if="resultJson" class="result-json">{{ resultJson }}</pre>
        <p v-else class="result-hint">查询真实任务后可查看解析结果与错误详情</p>
      </template>
    </el-drawer>

    <el-drawer v-model="logDrawer" title="解析日志" size="520px">
      <pre class="result-json">{{ logContent }}</pre>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import StatusTag from '@/components/StatusTag.vue'
import DemoBadge from '@/components/DemoBadge.vue'
import { useAppStore } from '@/stores/app'
import {
  getParseTask, getParseTaskErrors, getParseTaskResults, getFileArtifact,
  resumeParseTask, cancelParseTask, createParseTask
} from '@/api/parse'
import { hasToken } from '@/api/client'
import { isTerminalStatus, type ParseTask, type ParseFileItem } from '@/api/types'
import { unimplementedHint } from '@/api/dataSource'
import { fetchTasks, fetchEnginePanels, type TaskRow, type EnginePanel } from '@/api/mock/parsing'

const store = useAppStore()
const tasks = ref<TaskRow[]>([])
const panels = ref<EnginePanel[]>([])
const realTaskId = ref('')
const fileIdsInput = ref('')
const submitting = ref(false)
const lastCreated = ref<ParseTask | null>(null)
const polling = ref(false)

const drawer = ref(false)
const logDrawer = ref(false)
const detailRow = ref<TaskRow | null>(null)
const realDetail = ref<ParseTask | null>(null)
const resultJson = ref('')
const logContent = ref('')

const hasAuth = computed(() => hasToken())
const parsedFileIds = computed(() => fileIdsInput.value.split(/[\s,]+/).map((s) => s.trim()).filter(Boolean))
const fileIdsValid = computed(
  () => parsedFileIds.value.length > 0 &&
    parsedFileIds.value.length <= 20 &&
    parsedFileIds.value.every((id) => /^[0-9a-fA-F]{32}$/.test(id))
)
const canCreate = computed(() => hasAuth.value && fileIdsValid.value && !submitting.value)
const backendConfig = computed(() => {
  const i = store.serviceInfo
  if (!i) return null
  return [
    `provider: ${i.provider}`, `mode: ${i.mode}`, `enabled: ${i.enabled}`,
    `dual_engine_enabled: ${i.dual_engine_enabled}`, `database_enabled: ${i.database_enabled}`
  ]
})

function formatElapsed(s: number): string {
  return s < 60 ? `${s}s` : `${Math.floor(s / 60)}m${s % 60}s`
}

function formatFileError(e: ParseFileItem['error']): string {
  if (!e) return '—'
  if (typeof e === 'string') return e
  return e.message || e.code || '—'
}

function probe() {
  store.probeBackend()
}

async function load() {
  const [t, p] = await Promise.all([fetchTasks(), fetchEnginePanels()])
  tasks.value = t.data
  panels.value = p.data
}

/* ---------- 真实任务轮询：2s，终止态或 150 次后停止，组件卸载清理 ---------- */
let pollTimer: number | null = null
let pollTicks = 0

function stopPolling() {
  if (pollTimer !== null) {
    clearInterval(pollTimer)
    pollTimer = null
  }
  polling.value = false
}

async function startPolling(taskId: string) {
  stopPolling()
  if (isTerminalStatus(realDetail.value?.status || '')) return
  polling.value = true
  pollTicks = 0
  const tick = async () => {
    pollTicks++
    try {
      const t = await getParseTask(taskId)
      realDetail.value = t
      if (isTerminalStatus(t.status) || pollTicks >= 150) stopPolling()
    } catch {
      stopPolling()
    }
  }
  await tick()
  if (polling.value && pollTimer === null) pollTimer = window.setInterval(tick, 2000)
}

onBeforeUnmount(stopPolling)

/* ---------- 创建解析任务（真实接口，最小白名单请求体） ---------- */
async function submitTask() {
  if (!canCreate.value || submitting.value) return
  submitting.value = true
  try {
    const task = await createParseTask({ file_ids: parsedFileIds.value }, crypto.randomUUID())
    lastCreated.value = task
    realTaskId.value = task.task_id
    ElMessage.success(`解析任务已创建：${task.task_id}`)
  } catch {
    /* 拦截器已提示 */
  } finally {
    submitting.value = false
  }
}

/* ---------- 任务详情 ---------- */
function openDetail(row: TaskRow) {
  stopPolling()
  detailRow.value = row
  realDetail.value = null
  resultJson.value = ''
  drawer.value = true
}

async function queryRealTask() {
  const id = realTaskId.value.trim()
  if (!id) return
  if (!hasToken()) {
    ElMessage.warning('请先在系统监控页配置 API Token')
    return
  }
  stopPolling()
  try {
    const task = await getParseTask(id)
    realDetail.value = task
    detailRow.value = {
      taskId: task.task_id,
      fileName: task.files[0]?.file_name ?? task.task_id,
      docType: '—',
      pages: 0,
      engine: (task.files[0]?.selected_engine as TaskRow['engine']) ?? 'PaddleOCR',
      stage: task.status,
      progress: isTerminalStatus(task.status) ? 100 : 0,
      startedAt: task.created_at,
      elapsedSeconds: 0,
      status: (task.status as TaskRow['status']) ?? 'pending'
    }
    resultJson.value = ''
    drawer.value = true
    await startPolling(id)
  } catch {
    /* 拦截器已提示 */
  }
}

async function loadResults() {
  if (!realDetail.value) return
  try {
    resultJson.value = JSON.stringify(await getParseTaskResults(realDetail.value.task_id), null, 2)
  } catch { /* 已提示 */ }
}

async function loadErrors() {
  if (!realDetail.value) return
  try {
    resultJson.value = JSON.stringify(await getParseTaskErrors(realDetail.value.task_id), null, 2)
  } catch { /* 已提示 */ }
}

async function downloadArtifact() {
  if (!realDetail.value) return
  const taskId = realDetail.value.task_id
  const fileId = realDetail.value.files[0]?.file_id
  if (!fileId) {
    ElMessage.warning('该任务无可下载的解析产物')
    return
  }
  try {
    const buf = await getFileArtifact(taskId, fileId)
    const url = URL.createObjectURL(new Blob([buf], { type: 'application/octet-stream' }))
    const a = document.createElement('a')
    a.href = url
    a.download = `${taskId}-${fileId}-artifact.bin`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.info('已下载 artifact.bin（解析产物，非原始文件）')
  } catch { /* 已提示 */ }
}

async function retryReal() {
  if (!realDetail.value) return
  try {
    await ElMessageBox.confirm(`确认重试任务 ${realDetail.value.task_id}？`, '重试确认', { type: 'warning' })
    realDetail.value = await resumeParseTask(realDetail.value.task_id)
    ElMessage.success('重试请求已提交，后端返回最新任务状态')
    await startPolling(realDetail.value.task_id)
  } catch { /* 取消或失败 */ }
}

async function cancelReal() {
  if (!realDetail.value) return
  try {
    await ElMessageBox.confirm(`确认取消任务 ${realDetail.value.task_id}？`, '取消确认', { type: 'warning' })
    realDetail.value = await cancelParseTask(realDetail.value.task_id)
    ElMessage.success('取消请求已提交，后端返回最新任务状态')
  } catch { /* 取消或失败 */ }
}

function viewLogs(row: TaskRow) {
  if (realDetail.value && realDetail.value.task_id === row.taskId) {
    logContent.value = [
      '【来源】后端 public(task)；结构化日志接口 GET /api/parse/tasks/{id}/logs 尚未接入',
      `task_id   : ${realDetail.value.task_id}`,
      `status    : ${realDetail.value.status}`,
      `provider  : ${realDetail.value.provider}`,
      `created_at: ${realDetail.value.created_at}`,
      ...realDetail.value.files.map((f) =>
        `file ${f.file_id} | engine=${f.selected_engine || '—'} | status=${f.status} | fallback=${f.fallback_reason || '—'} | error=${formatFileError(f.error)}`
      )
    ].join('\n')
  } else {
    logContent.value = [
      '【DEMO 日志】非真实解析日志，仅用于展示交互',
      `[${row.startedAt}] 任务创建 ${row.taskId}`,
      `[路由] 演示引擎 ${row.engine}${row.fallbackReason ? `（${row.fallbackReason}）` : ''}`,
      `[阶段] ${row.stage}`,
      '真实日志需后端提供结构化日志接口'
    ].join('\n')
  }
  logDrawer.value = true
}

onMounted(() => {
  load()
  if (store.token) store.probeBackend()
})
</script>

<style scoped>
.card-head-title { font-weight: 600; }
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
.create-row { display: flex; gap: 12px; align-items: flex-start; }
.create-row :deep(.el-textarea) { flex: 1; }
.result-json { background: #0f2b52; color: #d6e4f7; padding: 14px; border-radius: 6px; font-size: 12px; line-height: 1.6; max-height: 360px; overflow: auto; white-space: pre-wrap; word-break: break-all; }
.result-hint { color: var(--mr-text-3); font-size: 13px; }
@media (max-width: 1366px) {
  .route-flow { flex-wrap: wrap; }
  .route-node { min-width: 200px; }
}
</style>
