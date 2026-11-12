<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h1 class="page-title">知识库入库管理</h1>
        <p class="page-desc">Chunk 结构预览与 public 知识库版本只读查询 —— 本页不创建版本、不嵌入、不发布、不写库</p>
      </div>
      <div class="header-tags">
        <el-tag type="success" effect="plain">真实接口 /api/knowledge/versions</el-tag>
        <el-tag :type="contractState === 'ready' ? 'success' : 'warning'" effect="plain">{{ contractLabel[contractState] }}</el-tag>
        <el-tooltip :content="disabledHint" placement="top">
          <span><el-button type="primary" disabled>发起入库批次</el-button></span>
        </el-tooltip>
      </div>
    </div>

    <!-- 只读边界：正式入库链路后端明确不支持 -->
    <el-alert
      type="warning"
      :closable="false"
      class="readonly-notice"
      title="本页只读：正式入库批次 / 发布 / 回滚接口均未实现"
      description="可调用的真实能力仅 4 个：POST /api/parse/tasks/{task_id}/files/{file_id}/preview、POST /api/review/{parse_id}/preview、GET /api/knowledge/versions、GET /api/knowledge/versions/{version}。预览返回 write_performed=false，门禁失败为 409 且不是空成功；版本列表只读 public schema，绝不读取 mvp_test_*。页面不生成任何批次、阶段进度、入库记录或法条数据。" />
    <div class="mr-disabled-hint" style="margin-bottom: 12px">{{ disabledHint }}</div>

    <!-- ① Chunk / 结构预览：两个真实 POST 接口 -->
    <el-card shadow="never">
      <template #header>
        <div class="card-head">
          <span>Chunk 结构预览 <span class="real-badge">REAL</span></span>
          <span class="card-sub">复用原有预览器 · 只输出 parents / chunks / tables / quality / warnings</span>
        </div>
      </template>

      <div class="preview-form">
        <el-radio-group v-model="previewSource" size="small">
          <el-radio-button label="task">任务文件预览</el-radio-button>
          <el-radio-button label="review">已持久化结果预览</el-radio-button>
        </el-radio-group>

        <template v-if="previewSource === 'task'">
          <el-input v-model="taskId" placeholder="task_id（来自解析中心任务列表）" clearable style="width: 260px" />
          <el-input v-model="taskFileId" placeholder="任务文件 ID（files[].file_id，≠ 上传 file_id）" clearable style="width: 300px" />
          <span class="route-hint">支持从解析中心「Chunk 预览」跳转自动回填</span>
        </template>
        <template v-else>
          <el-input v-model="parseId" placeholder="parse_id（database_parse_id，来自解析历史 / 审核队列）" clearable style="width: 420px" />
          <span class="route-hint">使用 document_review.documents 中已持久化的解析结果</span>
        </template>

        <el-select v-model="documentType" size="small" style="width: 130px">
          <el-option label="法规 law" value="law" />
          <el-option label="案例 case" value="case" />
        </el-select>
        <el-input-number v-model="maxChars" :min="100" :max="20000" :step="100" size="small" controls-position="right" style="width: 130px" />
        <el-button type="primary" size="small" :disabled="!canPreview" :loading="preview.loading.value" @click="runPreview">生成结构预览</el-button>
        <el-button size="small" :disabled="!hasRouteParams" @click="fillFromRoute">回填路由参数</el-button>
      </div>

      <div class="mr-disabled-hint" style="margin: 10px 0 12px">
        请求体仅含 <code>document_type</code> 与 <code>max_chars</code>（额外字段会 422）；法规表格等门禁失败返回 409，
        页面会显示错误态而非空结构。身份 ID 一律取自后端返回的 <code>file_mappings</code> / 解析历史，前端不拼接推导。
      </div>

      <AsyncPanel :state="preview.state.value" :error="preview.error.value" @retry="runPreview">
        <template #empty>
          <el-empty :image-size="60" description="尚未生成预览：填写后端返回的真实 ID 后点击「生成结构预览」" />
        </template>
        <div class="preview-result">
          <el-alert
            :type="preview.data.value?.write_performed ? 'error' : 'info'"
            :closable="false"
            :title="preview.data.value?.write_performed
              ? '异常：后端返回 write_performed=true，与契约不符，请停止联调并反馈后端'
              : `预览完成 · write_performed=${preview.data.value?.write_performed}（未发生任何写入）`"
            description="预览不创建版本、不嵌入向量、不发布、不自动认定法效。结构内容按不可信纯文本展示，不执行 HTML / 脚本。" />
          <el-tabs v-model="previewTab" class="preview-tabs">
            <el-tab-pane :label="`chunks（${chunkItems.length}）`" name="chunks" />
            <el-tab-pane :label="`parents（${parentItems.length}）`" name="parents" />
            <el-tab-pane :label="`tables（${tableItems.length}）`" name="tables" />
            <el-tab-pane label="quality" name="quality" />
            <el-tab-pane :label="`warnings（${warningItems.length}）`" name="warnings" />
            <el-tab-pane label="原始 JSON" name="raw" />
          </el-tabs>
          <div class="preview-body">
            <pre v-if="previewTab === 'chunks'" class="result-pre">{{ asJson(chunkItems) }}</pre>
            <pre v-else-if="previewTab === 'parents'" class="result-pre">{{ asJson(parentItems) }}</pre>
            <pre v-else-if="previewTab === 'tables'" class="result-pre">{{ asJson(tableItems) }}</pre>
            <pre v-else-if="previewTab === 'quality'" class="result-pre">{{ asJson(previewRaw.quality ?? {}) }}</pre>
            <pre v-else-if="previewTab === 'warnings'" class="result-pre">{{ asJson(warningItems) }}</pre>
            <pre v-else class="result-pre">{{ asJson(previewRaw) }}</pre>
          </div>
        </div>
      </AsyncPanel>
    </el-card>

    <!-- ② public 知识库版本列表 + 详情 -->
    <div class="card-grid version-grid">
      <el-card shadow="never">
        <template #header>
          <div class="card-head">
            <span>知识库版本 <span class="real-badge">REAL</span></span>
            <span class="card-sub">GET /api/knowledge/versions · public 只读</span>
          </div>
        </template>
        <AsyncPanel :state="versions.state.value" :error="versions.error.value" empty-text="public 知识库暂无版本记录（后端返回空列表）" @retry="versions.load()">
          <el-table :data="versions.data.value?.list || []" size="small" highlight-current-row @current-change="onSelectVersion">
            <el-table-column prop="kb_version" label="kb_version" min-width="170" show-overflow-tooltip />
            <el-table-column prop="status" label="状态" width="110" />
            <el-table-column label="ACTIVE" width="80">
              <template #default="{ row }">
                <el-tag size="small" :type="row.active ? 'success' : 'info'" effect="plain">{{ row.active ? '是' : '否' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="dimension" label="维度" width="80" align="right" />
            <el-table-column prop="created_at" label="创建时间" width="170">
              <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
            </el-table-column>
          </el-table>
          <div class="queue-pager">
            <el-pagination v-model:current-page="versionPage" :page-size="versionPageSize" :total="versions.data.value?.total || 0"
              layout="total, prev, pager, next" small background @current-change="versions.load()" />
          </div>
        </AsyncPanel>
      </el-card>

      <el-card shadow="never">
        <template #header>
          <div class="card-head">
            <span>版本详情 <span class="real-badge">REAL</span></span>
            <span class="card-sub">GET /api/knowledge/versions/{version}</span>
          </div>
        </template>
        <AsyncPanel :state="versionDetail.state.value" :error="versionDetail.error.value" @retry="versionDetail.load()">
          <template #empty>
            <el-empty :image-size="60" description="请在左侧版本列表选择一行，查看后端返回的真实版本详情" />
          </template>
          <el-descriptions :column="1" border size="small">
            <el-descriptions-item label="kb_version"><code class="mono">{{ versionDetail.data.value?.kb_version || '—' }}</code></el-descriptions-item>
            <el-descriptions-item label="status">{{ versionDetail.data.value?.status || '—' }}</el-descriptions-item>
            <el-descriptions-item label="active">{{ versionDetail.data.value?.active ? '是' : '否' }}</el-descriptions-item>
            <el-descriptions-item label="dimension">{{ versionDetail.data.value?.dimension ?? '—' }}</el-descriptions-item>
            <el-descriptions-item label="created_at">{{ formatTime(versionDetail.data.value?.created_at || '') }}</el-descriptions-item>
            <el-descriptions-item label="数据源">public schema（只读）</el-descriptions-item>
          </el-descriptions>
          <el-divider content-position="left">stats（后端原始字段，不做推算）</el-divider>
          <pre class="result-pre">{{ asJson(versionDetail.data.value?.stats ?? {}) }}</pre>
        </AsyncPanel>
      </el-card>
    </div>

    <!-- ③ 明确不支持的能力：不伪造批次 / 流水线 / 法规表 -->
    <el-card shadow="never" style="margin-top: 16px">
      <template #header>
        <div class="card-head">
          <span>正式入库能力状态（后端明确不支持）</span>
          <span class="card-sub">缺口清单来自 v0.2.2 契约，前端一律禁用或空态</span>
        </div>
      </template>
      <el-table :data="ingestionGaps" size="small">
        <el-table-column label="优先级" width="90">
          <template #default="{ row }">
            <el-tag :type="row.priority === 'P0' ? 'danger' : 'info'" size="small" effect="plain">{{ row.priority }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="api" label="缺失接口" min-width="300" show-overflow-tooltip />
        <el-table-column prop="usage" label="对应业务" min-width="200" show-overflow-tooltip />
        <el-table-column prop="impact" label="本页处理" min-width="260" show-overflow-tooltip />
      </el-table>
      <div class="mr-disabled-hint" style="margin-top: 10px">
        七阶段流水线、批次四态、法规数据表与入库记录均没有真实 HTTP 数据源，v0.2.2 起不再以 DEMO 形式呈现；
        后端补齐批次授权 / 版本一致性 / 发布回滚接口并通过契约验收后，方可解除禁用。
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import AsyncPanel from '@/components/AsyncPanel.vue'
import { useAsyncData } from '@/composables/useAsyncData'
import {
  previewTaskFile, previewReviewResult, listKbVersions, getKbVersion
} from '@/api/frontend'
import {
  contractState, contractLabel, unimplementedHint, MISSING_CAPABILITIES
} from '@/api/dataSource'
import type {
  PreviewResponse, PreviewRequest, KbVersionList, VersionInfo, KbVersionItem
} from '@/api/types'

/**
 * v0.2.2 入库管理（只读）
 * - 预览 = 两个真实 POST，write_performed 恒 false；409 门禁失败按错误态呈现，不渲染空结构
 * - 版本 = GET /api/knowledge/versions + /{version}，只读 public，绝不读 mvp_test_*
 * - 正式入库批次 / 发布 / 回滚 / precheck / version-check 后端明确不支持 → 全部禁用，零 DEMO 业务数据
 * - 身份 ID 从后端 file_mappings / 解析历史 / 审核队列取得；解析中心通过 ?task=&file= 跳转回填
 */
const route = useRoute()

const disabledHint = unimplementedHint(
  'POST /api/ingestion/batches（批次授权）+ POST /api/ingestion/publish、/rollback + POST /api/ingestion/precheck + GET /api/ingestion/version-check'
) + '；预览成功不等于正式入库成功，前端不执行任何数据库写入'

const ingestionGaps = MISSING_CAPABILITIES.filter((m) => m.api.includes('/api/ingestion/'))

/* ───────── Chunk 结构预览 ───────── */
const previewSource = ref<'task' | 'review'>('task')
const taskId = ref(String(route.query.task || ''))
const taskFileId = ref(String(route.query.file || ''))
const parseId = ref(String(route.query.parse || ''))
const documentType = ref<PreviewRequest['document_type']>('law')
const maxChars = ref(800)
const previewTab = ref('chunks')

const hasRouteParams = computed(() =>
  !!(route.query.task || route.query.file || route.query.parse)
)

const canPreview = computed(() => {
  if (preview.loading.value) return false
  if (maxChars.value < 100 || maxChars.value > 20000) return false
  return previewSource.value === 'task'
    ? !!(taskId.value.trim() && taskFileId.value.trim())
    : !!parseId.value.trim()
})

function previewBody(): PreviewRequest {
  return { document_type: documentType.value, max_chars: maxChars.value }
}

const preview = useAsyncData<PreviewResponse>(
  (signal) => previewSource.value === 'task'
    ? previewTaskFile(taskId.value.trim(), taskFileId.value.trim(), previewBody(), signal)
    : previewReviewResult(parseId.value.trim(), previewBody(), signal),
  { immediate: false, isEmpty: () => false }
)
preview.state.value = 'empty'

function runPreview() {
  if (!canPreview.value) return
  previewTab.value = 'chunks'
  void preview.load()
}

function fillFromRoute() {
  taskId.value = String(route.query.task || '')
  taskFileId.value = String(route.query.file || '')
  parseId.value = String(route.query.parse || '')
}

type AnyRecord = Record<string, unknown>
const previewRaw = computed<AnyRecord>(() => preview.data.value?.preview || {})
function asList(value: unknown): unknown[] {
  return Array.isArray(value) ? value : []
}
const chunkItems = computed(() => asList(previewRaw.value.chunks))
const parentItems = computed(() => asList(previewRaw.value.parents))
const tableItems = computed(() => asList(previewRaw.value.tables))
const warningItems = computed(() => asList(previewRaw.value.warnings))
function asJson(value: unknown): string {
  if (value == null || (Array.isArray(value) && value.length === 0) ||
      (typeof value === 'object' && !Array.isArray(value) && Object.keys(value as object).length === 0)) {
    return '〔后端未返回该结构字段，不伪造占位数据〕'
  }
  return JSON.stringify(value, null, 2)
}

/* ───────── public 知识库版本 ───────── */
const versionPage = ref(1)
const versionPageSize = 10
const selectedVersion = ref('')

const versions = useAsyncData<KbVersionList>(
  (signal) => listKbVersions({ page: versionPage.value, pageSize: versionPageSize }, signal)
)
const versionDetail = useAsyncData<VersionInfo>(
  (signal) => getKbVersion(selectedVersion.value, signal),
  { immediate: false, isEmpty: () => false }
)
versionDetail.state.value = 'empty'

function onSelectVersion(row: KbVersionItem | null) {
  if (!row?.kb_version) return
  selectedVersion.value = row.kb_version
  void versionDetail.load()
}

function formatTime(v: string) { return v ? String(v).replace('T', ' ').slice(0, 19) : '—' }
</script>

<style scoped>
.header-tags { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.readonly-notice { margin-bottom: 12px; }
.card-head { display: flex; justify-content: space-between; align-items: center; font-weight: 600; gap: 12px; }
.card-sub { font-weight: 400; font-size: 12px; color: var(--mr-text-3); }
.preview-form { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.route-hint { font-size: 12px; color: var(--mr-text-3); }
.preview-tabs :deep(.el-tabs__header) { margin: 0 0 8px; }
.preview-body { max-height: 340px; overflow-y: auto; padding: 10px; border: 1px solid var(--mr-line); border-radius: 6px; background: #fafbfe; }
.result-pre { font-family: var(--mr-font); font-size: 12px; line-height: 1.8; white-space: pre-wrap; word-break: break-word; margin: 0; max-width: 100%; }
.version-grid { grid-template-columns: 1.5fr 1fr; margin-top: 16px; }
.queue-pager { display: flex; justify-content: flex-end; margin-top: 10px; }
.mono { font-family: monospace; font-size: 12px; }
@media (max-width: 1366px) {
  .version-grid { grid-template-columns: 1fr; }
}
</style>
