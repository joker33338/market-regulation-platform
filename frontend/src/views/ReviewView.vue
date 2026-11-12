<template>
  <div class="page review-page">
    <div class="page-header">
      <div>
        <h1 class="page-title">文档审核中心</h1>
        <p class="page-desc">解析结果人工复核 —— 原始解析结果只读，人工修订须留痕，不得覆盖原始证据文件</p>
      </div>
      <div class="header-tags">
        <el-tag :type="writeGate === 'enabled' ? 'success' : 'warning'" effect="plain">{{ writeGateLabel }}</el-tag>
        <el-tag :type="contractState === 'ready' ? 'success' : 'warning'" effect="plain">{{ contractLabel[contractState] }}</el-tag>
      </div>
    </div>

    <el-alert :type="writeGate === 'enabled' ? 'success' : 'warning'" :closable="false" class="review-notice"
      :title="writeGateTitle" :description="writeGateDescription" />

    <!-- 待复核队列：真实完整语义接口；高度可由下方分隔条上下拖动调整 -->
    <el-card shadow="never" class="queue-card" :class="{ resizable: queueHeight !== null }" :style="queueStyle">
      <template #header>
        <div class="card-head">
          <span>待复核队列 <span class="real-badge">REAL</span></span>
          <span class="card-sub">GET /api/review?requires_review=true · 数据源 document_review.documents</span>
        </div>
      </template>
      <AsyncPanel :state="queue.state.value" :error="queue.error.value" empty-text="当前没有待人工复核的文档（后端返回空列表）" @retry="queue.load()">
        <el-table :data="queue.data.value?.list || []" size="small" highlight-current-row max-height="220" @current-change="onSelectQueue">
          <el-table-column prop="file_name" label="文件名称" min-width="220" show-overflow-tooltip />
          <el-table-column prop="parsing_status" label="解析状态" width="110" />
          <el-table-column label="需复核" width="80"><template #default="{ row }"><el-tag size="small" :type="row.requires_review ? 'warning' : 'info'" effect="plain">{{ row.requires_review ? '是' : '否' }}</el-tag></template></el-table-column>
          <el-table-column prop="imported_at" label="入库时间" width="170"><template #default="{ row }">{{ formatTime(row.imported_at) }}</template></el-table-column>
          <el-table-column label="parse_id" min-width="160" show-overflow-tooltip><template #default="{ row }"><code class="mono">{{ row.parse_id }}</code></template></el-table-column>
        </el-table>
        <div class="queue-pager">
          <el-pagination v-model:current-page="queuePage" :page-size="queuePageSize" :total="queue.data.value?.total || 0"
            layout="total, prev, pager, next" small background @current-change="queue.load()" />
        </div>
      </AsyncPanel>
    </el-card>

    <!-- 上下拖动分隔条 + 两栏同时放大：便于左边原文与右边解析结果对照 -->
    <div class="split-toolbar" :class="{ 'on-top': expandedPane === 'both' }">
      <div class="v-resizer" :class="{ disabled: expandedPane === 'both' }"
        title="按住上下拖动，调整队列与对比区域高度；双击恢复默认" @mousedown.prevent="startResize" @dblclick="resetResize">
        <span class="v-resizer-grip">⋮⋮</span>
        <span>{{ expandedPane === 'both' ? '对照放大中 · 按 Esc 或点击空白区域还原' : '上下拖动调整对比区高度（双击恢复默认）' }}</span>
        <span class="v-resizer-grip">⋮⋮</span>
      </div>
      <el-button class="both-expand-btn" size="small" :icon="expandedPane === 'both' ? Close : FullScreen"
        title="左右两栏同时放大，便于原文与解析结果对照；按 Esc 或点击空白区域还原"
        @click="togglePane('both')">
        {{ expandedPane === 'both' ? '退出对照放大' : '对照放大（两栏）' }}
      </el-button>
    </div>

    <!-- 左右双栏 -->
    <div class="review-split" :class="{ 'expanded-both': expandedPane === 'both' }">
      <el-card shadow="never" class="pane" :class="{ expanded: expandedPane === 'preview' }"
        :body-style="{ padding: 0, display: 'flex', flexDirection: 'column', flex: '1 1 auto', minHeight: 0 }">
        <div class="pane-toolbar">
          <div class="pane-head-left">
            <span class="pane-title">原始文件预览</span>
            <span class="source-hint">GET /api/parse/files/{source_file_id}/source</span>
          </div>
          <el-button class="expand-btn" size="small" :icon="expandedPane === 'preview' ? Close : FullScreen"
            title="放大后可按 Esc 或点击空白区域还原" @click="togglePane('preview')">
            {{ expandedPane === 'preview' ? '还原' : '单独放大' }}
          </el-button>
        </div>
        <div class="preview-body">
          <DocumentPreview
            :file-id="detail.data.value?.source_file_id || ''"
            :file-name="detail.data.value?.file_name || ''"
            :expected-sha256="expectedSha256"
            v-model:page="currentPage"
            :total-pages="totalPages"
          />
        </div>
      </el-card>

      <el-card shadow="never" class="pane" :class="{ expanded: expandedPane === 'result' }"
        :body-style="{ padding: 0, display: 'flex', flexDirection: 'column', flex: '1 1 auto', minHeight: 0 }">
        <div class="pane-toolbar">
          <el-tabs v-model="resultTab" class="result-tabs">
            <el-tab-pane label="OCR 文本" name="text" />
            <el-tab-pane label="Markdown" name="markdown" />
            <el-tab-pane label="JSON" name="json" />
            <el-tab-pane label="表格结构" name="table" />
            <el-tab-pane label="质量指标" name="quality" />
            <el-tab-pane label="候选对照" name="candidate" />
            <el-tab-pane v-if="eventsSupported" label="审核台账" name="ledger" />
          </el-tabs>
          <el-button class="expand-btn" size="small" :icon="expandedPane === 'result' ? Close : FullScreen"
            title="放大后可按 Esc 或点击空白区域还原" @click="togglePane('result')">
            {{ expandedPane === 'result' ? '还原' : '单独放大' }}
          </el-button>
        </div>

        <AsyncPanel :state="detail.state.value" :error="detail.error.value" empty-text="请从上方待复核队列选择一条记录" @retry="detail.load()">
          <!-- 按页关联 -->
          <div class="page-link">
            <el-icon><Connection /></el-icon>
            <span>按页对照 · 当前第 <b class="num">{{ currentPage }}</b> / {{ totalPages }} 页</span>
            <span class="page-link-text">{{ pageLinkText }}</span>
            <span v-if="pageTableCount" class="page-link-tables num">该页 {{ pageTableCount }} 个表格</span>
          </div>

          <div class="result-body">
            <pre v-if="resultTab === 'text'" class="result-pre">{{ pageText || '〔后端未返回该页 OCR 文本〕' }}</pre>
            <pre v-else-if="resultTab === 'markdown'" class="result-pre">{{ detail.data.value?.markdown_content || '〔后端未返回 Markdown〕' }}</pre>
            <pre v-else-if="resultTab === 'json'" class="result-pre">{{ originalResultJson }}</pre>

            <div v-else-if="resultTab === 'table'" class="table-pane">
              <el-alert type="info" :closable="false" style="margin-bottom: 12px"
                title="表格内容来自 original_result.tables（不可信内容，按纯文本展示）"
                description="后端未提供表格 HTML 渲染契约，前端不执行任何 HTML / 脚本，也不生成占位表格数据。" />
              <div v-if="tableItems.length" class="table-list">
                <div v-for="(t, i) in tableItems" :key="i" class="table-item">
                  <div class="table-item-head">表格 {{ i + 1 }} <span class="num">{{ tableShape(t) }}</span></div>
                  <pre class="result-pre">{{ JSON.stringify(t, null, 2) }}</pre>
                </div>
              </div>
              <el-empty v-else :image-size="60" description="后端未返回表格结构数据" />
            </div>

            <div v-else-if="resultTab === 'quality'" class="quality-pane">
              <div class="quality-grid">
                <div class="quality-item"><span class="num quality-value">{{ detail.data.value?.requires_review ? '是' : '否' }}</span><span class="quality-label">需人工复核</span></div>
                <div class="quality-item"><span class="num quality-value">{{ qualityEntries.length }}</span><span class="quality-label">质量字段数</span></div>
                <div class="quality-item"><span class="num quality-value">{{ totalPages }}</span><span class="quality-label">页结构数</span></div>
                <div class="quality-item"><span class="num quality-value">{{ tableItems.length }}</span><span class="quality-label">表格数</span></div>
              </div>
              <el-divider content-position="left">后端 quality 原始字段</el-divider>
              <el-table v-if="qualityEntries.length" :data="qualityEntries" size="small" border>
                <el-table-column prop="key" label="字段" width="200" />
                <el-table-column prop="value" label="值（原始）" show-overflow-tooltip />
              </el-table>
              <el-empty v-else :image-size="60" description="后端未返回质量指标" />
              <el-divider content-position="left">需要人工复核的原因</el-divider>
              <p class="hint-text">
                requires_review = <b>{{ detail.data.value?.requires_review }}</b>。
                {{ reviewReason }}
              </p>
            </div>

            <div v-else-if="resultTab === 'ledger'" class="ledger-pane">
              <div class="ledger-summary">
                <span>台账可用：<b>{{ ledger?.available ? '是' : '否' }}</b></span>
                <span>台账状态：<b>{{ ledger?.status || '—' }}</b></span>
                <span>版本：<b class="num">{{ expectedVersion }}</b></span>
                <span>当前修订：<code class="mono">{{ ledger?.current_revision || '—' }}</code></span>
                <el-button size="small" text type="primary" @click="events.load()">刷新事件</el-button>
              </div>
              <AsyncPanel :state="events.state.value" :error="events.error.value" empty-text="该对象暂无审核台账事件" @retry="events.load()">
                <el-table :data="events.data.value?.list || []" size="small" max-height="300">
                  <el-table-column prop="version" label="版本" width="80" />
                  <el-table-column prop="action" label="动作" width="140" />
                  <el-table-column prop="status" label="台账状态" width="130" />
                  <el-table-column prop="operator" label="操作者" width="130" />
                  <el-table-column label="时间" width="170"><template #default="{ row }">{{ formatTime(row.timestamp) }}</template></el-table-column>
                  <el-table-column label="理由 / 修订正文" min-width="240" show-overflow-tooltip>
                    <template #default="{ row }"><span>{{ row.content || row.reason || '—' }}</span></template>
                  </el-table-column>
                </el-table>
                <div v-if="latestRevision" class="revision-box">
                  <div class="revision-head">最近人工修订（不可信文本，仅纯文本展示，不执行 HTML）</div>
                  <pre class="result-pre">{{ latestRevision.content }}</pre>
                </div>
              </AsyncPanel>
              <el-alert v-if="lastReceipt" type="success" :closable="false" style="margin-top: 12px"
                :title="`最近写入回执：${lastReceipt.action} · 版本 ${lastReceipt.version} · write_performed=${lastReceipt.write_performed}`"
                :description="`event_id=${lastReceipt.event_id}；original_result_modified=${lastReceipt.original_result_modified}；publish_authorized=${lastReceipt.publish_authorized}；reparse_task_created=${lastReceipt.reparse_task_created}`" />
            </div>

            <div v-else class="candidate-pane">
              <el-alert v-if="!detail.data.value?.local_candidate_available" type="warning" :closable="false" style="margin-bottom: 12px"
                title="本地候选不可用"
                description="local_candidate_available=false：本地 checkpoint 未保留或身份无法核验。后端禁止伪造对照，本页不生成模拟候选内容。" />
              <el-divider content-position="left">最终候选（original_result，后端真实）</el-divider>
              <pre class="result-pre">{{ originalResultJson }}</pre>
              <el-divider content-position="left">本地候选（local_candidate）</el-divider>
              <pre class="result-pre">{{ detail.data.value?.local_candidate ? JSON.stringify(detail.data.value.local_candidate, null, 2) : '〔后端未返回本地候选，不伪造〕' }}</pre>
              <p class="hint-text">最终候选以 original_result 为准；原始解析结果与原始证据文件均保持只读，人工修订须由后端写入接口追加新版本并留审计记录。</p>
            </div>
          </div>

          <div class="meta-bar">
            <span>文件：<b>{{ detail.data.value?.file_name || '—' }}</b></span>
            <span>parse_id：<code class="mono">{{ detail.data.value?.parse_id || '—' }}</code></span>
            <span>task_id：<code class="mono">{{ detail.data.value?.task_id || '—' }}</code></span>
            <span>解析状态：<b>{{ detail.data.value?.parsing_status || '—' }}</b></span>
            <span>结果来源：document_review.documents</span>
            <span>SHA256：<code class="mono">{{ expectedSha256 ? expectedSha256.slice(0, 16) + '…' : '由 /source 响应头校验' }}</code></span>
            <span v-if="ledger">台账：v{{ expectedVersion }} / {{ ledger.status || '—' }}（{{ detail.data.value?.review_write_supported ? '已获写授权' : '未获写授权' }}）</span>
          </div>
        </AsyncPanel>

        <!-- 底部操作：运行期契约 + 审核详情双门控；未通过时保持禁用，绝不本地假成功 -->
        <div class="action-bar">
          <el-tooltip v-for="a in actions" :key="a.key" :content="actionHint" placement="top" :disabled="canWrite">
            <span>
              <el-button :type="a.type" :disabled="!canWrite" :loading="busy && activeAction === a.key" @click="openAction(a.key)">
                {{ a.label }}
              </el-button>
            </span>
          </el-tooltip>
          <el-button v-if="canWrite" size="small" text type="primary" :loading="detail.loading.value" @click="refreshAfterWrite">刷新台账</el-button>
        </div>
        <div class="action-hint" :class="canWrite ? '' : 'mr-disabled-hint'">{{ actionHint }}</div>
      </el-card>
    </div>

    <!-- 放大态遮罩：点击空白或按 Esc 还原。只切换外层定位，不销毁左右栏 DOM，PDF iframe 保持当前页 -->
    <div v-if="expandedPane" class="pane-backdrop" @click="expandedPane = null" />

    <!-- 审核写入确认：只有双门控通过才可打开；提交结果以后端回执 write_performed 为准 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="620px" :close-on-click-modal="false" @closed="resetDialog">
      <el-alert type="info" :closable="false" style="margin-bottom: 12px"
        :title="`台账版本 ${expectedVersion} · ${currentParseId}`"
        description="提交会带 Idempotency-Key 与 expected_version。操作者由会话凭证对应的 owner 决定，客户端不指定；审核通过不授予发布权限、不自动创建解析任务，原始解析结果与原件保持只读。" />
      <el-form class="action-form" label-width="96px">
        <el-form-item v-if="activeAction === 'approve'" label="备注（可选）">
          <el-input v-model="form.reason" type="textarea" :rows="3" maxlength="2000" show-word-limit placeholder="可留空，前端不会生成假备注" />
        </el-form-item>
        <el-form-item v-if="activeAction === 'reject'" label="退回理由" required>
          <el-input v-model="form.reason" type="textarea" :rows="4" maxlength="2000" show-word-limit placeholder="必填，随审核事件留痕" />
        </el-form-item>
        <template v-if="activeAction === 'mark-error'">
          <el-form-item label="错误理由" required>
            <el-input v-model="form.reason" type="textarea" :rows="4" maxlength="2000" show-word-limit placeholder="必填" />
          </el-form-item>
          <el-form-item label="页码" required>
            <el-input-number v-model="form.page" :min="1" :max="totalPages" />
            <span class="form-hint">须对应原始解析结果中的真实 page_number（当前对照第 {{ currentPage }} 页）</span>
          </el-form-item>
          <el-form-item label="定位片段">
            <el-input v-model="form.span" maxlength="2000" placeholder="可选 span" />
          </el-form-item>
        </template>
        <template v-if="activeAction === 'save-revision'">
          <el-form-item label="页码" required>
            <el-input-number v-model="form.page" :min="1" :max="totalPages" />
          </el-form-item>
          <el-form-item label="修订正文" required>
            <el-input v-model="form.content" type="textarea" :rows="9" maxlength="200000" show-word-limit
              placeholder="原样保存，保留前导空格与换行；按不可信纯文本渲染，不执行 HTML" />
          </el-form-item>
        </template>
      </el-form>
      <el-alert v-if="submitError" type="error" :closable="false" :title="submitError" />
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="busy" :disabled="!formValid" @click="submitAction">确认提交</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Connection, FullScreen, Close } from '@element-plus/icons-vue'
import AsyncPanel from '@/components/AsyncPanel.vue'
import DocumentPreview from '@/components/document/DocumentPreview.vue'
import { useAsyncData } from '@/composables/useAsyncData'
import { listReviews, getReviewDetail } from '@/api/frontend'
import { toApiError } from '@/api/errors'
import {
  contractState, contractLabel, hasV023ReviewWriteRoutes, hasV023ReviewEvents
} from '@/api/dataSource'
import {
  approveReview, rejectReview, markReviewError, saveReviewRevision,
  getReviewEvents, newIdempotencyKey
} from '@/api/reviewWrite'
import type {
  ReviewDetail, ReviewQueue, ReviewQueueItem, ReviewEvent, ReviewReceipt, ListResponse
} from '@/api/types'

/**
 * v0.2.2 审核中心：
 * - 队列 = GET /api/review（完整语义，后端读 document_review.documents，不依赖 v_review_queue）
 * - 详情 = GET /api/review/{parse_id}（raw_text / markdown / original_result / quality / 候选对照）
 * - 原件 = /source 授权字节，SHA256 由后端 X-SHA256 校验
 * - 写操作（v0.2.3）：双门控 = 运行期 OpenAPI 含 4 条写路径 + 详情 review_write_supported / review_ledger.available
 *   正式 8180 当前仍是 0.2.2-api-candidate / 22 路径，第一道门控必然不通过，按钮保持禁用。
 * - 提交必带 Idempotency-Key 与 expected_version；409/403/401/422/503 分别给出明确提示，不隐藏错误。
 * - 成功与否以后端回执 write_performed 为准，前端不改本地状态、不伪造事件。
 * - Markdown / 表格 / 人工修订一律纯文本，不使用 v-html，不执行不可信 HTML。
 */

const queuePage = ref(1)
const queuePageSize = 10
const currentParseId = ref('')
const currentPage = ref(1)
const resultTab = ref('text')

/**
 * 放大查看：只切换外层容器的定位，不销毁/重建左右栏 DOM。
 * 这样 V022-F01 的 PDF iframe 与 Blob URL 生命周期保持连续，放大后仍可翻页/缩放。
 */
type ExpandablePane = 'preview' | 'result' | 'both' | null
const expandedPane = ref<ExpandablePane>(null)
function togglePane(which: 'preview' | 'result' | 'both') {
  expandedPane.value = expandedPane.value === which ? null : which
}
function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && expandedPane.value) expandedPane.value = null
}
onMounted(() => window.addEventListener('keydown', onKeydown))

/* 上下拖动：调整「待复核队列」与「左右对比区」的高度分配。
   只在本地改容器高度，不触发任何接口请求，也不改动业务数据。 */
const queueHeight = ref<number | null>(null)
const queueStyle = computed(() => queueHeight.value == null ? {} : { height: `${queueHeight.value}px` })
let resizeStartY = 0
let resizeStartH = 0
function startResize(e: MouseEvent) {
  if (expandedPane.value) return // 放大态下分栏已脱离文档流，拖动无意义
  const card = document.querySelector('.queue-card') as HTMLElement | null
  if (!card) return
  resizeStartY = e.clientY
  resizeStartH = card.getBoundingClientRect().height
  queueHeight.value = resizeStartH // 先固化当前高度，避免首帧跳动
  window.addEventListener('mousemove', onResize)
  window.addEventListener('mouseup', stopResize)
}
function onResize(e: MouseEvent) {
  const max = Math.max(160, window.innerHeight - 280)
  queueHeight.value = Math.min(max, Math.max(110, resizeStartH + e.clientY - resizeStartY))
}
function stopResize() {
  window.removeEventListener('mousemove', onResize)
  window.removeEventListener('mouseup', stopResize)
}
function resetResize() { queueHeight.value = null }

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown)
  stopResize()
})

const queue = useAsyncData<ReviewQueue>(
  (signal) => listReviews({ page: queuePage.value, pageSize: queuePageSize, requiresReview: true }, signal)
)
const detail = useAsyncData<ReviewDetail>(
  (signal) => getReviewDetail(currentParseId.value, signal),
  { immediate: false, isEmpty: () => false }
)
// 尚未选择队列记录时显示明确空态，而非无限 loading
detail.state.value = 'empty'

type ReviewActionKey = 'approve' | 'reject' | 'mark-error' | 'save-revision'
const actions = [
  { key: 'approve', label: '审核通过', type: 'success' },
  { key: 'reject', label: '退回重新解析', type: 'warning' },
  { key: 'mark-error', label: '标记识别错误', type: 'danger' },
  { key: 'save-revision', label: '保存人工修订', type: 'primary' }
] as const

/* ───────── 运行期能力 + 审核详情双门控 ───────── */
const contractWriteSupported = computed(() => hasV023ReviewWriteRoutes())
const eventsSupported = computed(() => hasV023ReviewEvents())
const ledger = computed(() => detail.data.value?.review_ledger ?? null)
const detailWriteSupported = computed(() =>
  detail.data.value?.review_write_supported === true && ledger.value?.available === true
)
const busy = ref(false)
const canWrite = computed(() =>
  contractWriteSupported.value && detailWriteSupported.value &&
  !!currentParseId.value && !busy.value
)
const expectedVersion = computed(() => ledger.value?.version ?? 0)

type WriteGate = 'contract-missing' | 'detail-locked' | 'enabled'
const writeGate = computed<WriteGate>(() => {
  if (!contractWriteSupported.value) return 'contract-missing'
  if (!detailWriteSupported.value) return 'detail-locked'
  return 'enabled'
})
const writeGateLabel = computed(() => ({
  'contract-missing': '审核写入未启用 · 运行期契约未加载 v0.2.3',
  'detail-locked': '审核写入未解锁 · 台账或写授权未就绪',
  enabled: '审核写入已启用 · 真实台账'
}[writeGate.value]))
const writeGateTitle = computed(() => ({
  'contract-missing': '当前运行服务未加载审核台账接口，四个写操作保持禁用',
  'detail-locked': '当前对象的审核台账不可用或当前凭证未获写授权，写操作保持禁用',
  enabled: '已按运行期契约与审核详情启用真实审核写入'
}[writeGate.value]))
const writeGateDescription = computed(() => ({
  'contract-missing': '队列 / 详情 / 原件仍来自真实只读接口。v0.2.3 审核写入接口虽已在后端源码分支交付，但活动服务的 GET /api/openapi.json 未返回这 4 条路径，前端不提前解锁、不调用不存在的接口。',
  'detail-locked': '写按钮还须逐对象确认详情返回 review_write_supported=true 且 review_ledger.available=true；台账未配置、存储异常或当前 owner 不在 writers 名单时均不置 true。requires_review 只是 OCR 复核信号，不能推导台账状态。',
  enabled: '写操作使用 Idempotency-Key + expected_version 版本锁；操作者由 Token→owner 决定。审核通过不授予发布权限、不自动创建解析任务，原始解析结果与原件始终只读。'
}[writeGate.value]))
const actionHint = computed(() => {
  if (writeGate.value === 'contract-missing') {
    return '运行期 OpenAPI 未加载 v0.2.3 审核写入路由（当前正式服务仍为 0.2.2-api-candidate / 22 路径），按钮保持禁用，不提前解锁、不伪造成功。'
  }
  if (writeGate.value === 'detail-locked') {
    return `当前对象台账不可用或当前凭证未获写授权（review_write_supported=${String(detail.data.value?.review_write_supported ?? false)}、available=${String(ledger.value?.available ?? false)}）${ledger.value?.reason ? `，原因：${ledger.value.reason}` : ''}；按钮保持禁用。`
  }
  return `已启用真实写入：台账 v${expectedVersion.value} / ${ledger.value?.status || '—'}。提交后以后端回执 write_performed 判定成功，并追加事件留痕。`
})

/* ───────── 台账事件（仅 v0.2.3 运行期契约具备时才请求） ───────── */
const events = useAsyncData<ListResponse<ReviewEvent>>(
  (signal) => getReviewEvents(currentParseId.value, { page: 1, pageSize: 50 }, signal),
  { immediate: false }
)
events.state.value = 'empty'
const latestRevision = computed(() =>
  (events.data.value?.list || []).find((e) => e.action === 'save-revision' && typeof e.content === 'string') || null
)
const lastReceipt = ref<ReviewReceipt | null>(null)

watch(resultTab, (tab) => {
  if (tab === 'ledger' && eventsSupported.value && currentParseId.value) void events.load()
})

/* ───────── 写入确认弹窗 ───────── */
const dialogVisible = ref(false)
const activeAction = ref<ReviewActionKey>('approve')
const idempotencyKey = ref('')
const submitError = ref('')
const form = reactive({ reason: '', page: 1, span: '', content: '' })
const dialogTitle = computed(() => ({
  approve: '确认审核通过', reject: '确认退回重新解析',
  'mark-error': '确认标记识别错误', 'save-revision': '确认保存人工修订'
}[activeAction.value]))
const formValid = computed(() => {
  const a = activeAction.value
  if (a === 'approve') return true
  if (a === 'reject' || a === 'mark-error') return form.reason.length > 0
  return form.content.length > 0 && Number.isInteger(form.page) && form.page >= 1
})

function resetDialog() {
  submitError.value = ''
  form.reason = ''
  form.span = ''
  form.content = ''
  form.page = currentPage.value
}
function openAction(key: ReviewActionKey) {
  if (!canWrite.value) return
  activeAction.value = key
  idempotencyKey.value = newIdempotencyKey() // 一次操作一个键，失败重试沿用同键同 body
  submitError.value = ''
  form.reason = ''
  form.span = ''
  form.content = ''
  form.page = currentPage.value
  dialogVisible.value = true
}

async function submitAction() {
  if (!canWrite.value || !formValid.value) return
  busy.value = true
  submitError.value = ''
  const parseId = currentParseId.value
  const version = expectedVersion.value
  const key = idempotencyKey.value
  try {
    let receipt: ReviewReceipt
    if (activeAction.value === 'approve') {
      receipt = await approveReview(parseId, version, key, form.reason || undefined)
    } else if (activeAction.value === 'reject') {
      receipt = await rejectReview(parseId, version, form.reason, key)
    } else if (activeAction.value === 'mark-error') {
      receipt = await markReviewError(parseId, version, form.reason, form.page, form.span || undefined, key)
    } else {
      // content 原样提交：前导空格与换行是人工正文的一部分，不做 trim
      receipt = await saveReviewRevision(parseId, version, form.page, form.content, key)
    }
    if (!receipt || receipt.write_performed !== true) {
      const hint = '后端回执未确认写入（write_performed 非 true），前端不判定为成功。'
      submitError.value = hint
      ElMessage.warning(hint)
      return
    }
    lastReceipt.value = receipt
    dialogVisible.value = false
    ElMessage.success(`审核写入成功：${receipt.action} · 台账 v${receipt.version}（event_id ${receipt.event_id.slice(0, 8)}…）`)
    await Promise.all([
      detail.load(),
      eventsSupported.value ? events.load() : Promise.resolve()
    ])
  } catch (err) {
    const e = toApiError(err)
    let hint = e.hint
    if (e.status === 409) {
      hint = '写入被拒绝（409）：台账版本或原始结果已变化，或同一幂等键复用了不同请求。已刷新详情，请确认后重试。'
      idempotencyKey.value = newIdempotencyKey()
      void detail.load()
    } else if (e.status === 403) {
      hint = '无权写入（403）：当前会话凭证对应的 owner 未被配置为审核写入者。'
    } else if (e.status === 401) {
      hint = '凭证失效或未认证（401）：请重新配置 API Token 后再试。'
    } else if (e.status === 422) {
      hint = '参数被拒绝（422）：请检查必填理由、页码是否对应真实 page_number，以及是否传入契约外字段。'
    } else if (e.status === 503) {
      hint = '审核台账未配置或存储暂不可用（503），本次未执行写入。'
    }
    submitError.value = hint
    ElMessage.error(hint)
  } finally {
    busy.value = false
  }
}

async function refreshAfterWrite() {
  await detail.load()
  if (eventsSupported.value) await events.load()
}

function onSelectQueue(row: ReviewQueueItem | null) {
  if (!row?.parse_id) return
  currentParseId.value = row.parse_id
  currentPage.value = 1
  resultTab.value = 'text'
  lastReceipt.value = null
  submitError.value = ''
  void detail.load()
  if (eventsSupported.value) void events.load()
}

/* ───────── 按页关联与真实结果字段 ───────── */
type AnyRecord = Record<string, unknown>

function asRecords(value: unknown): AnyRecord[] {
  return Array.isArray(value) ? (value as AnyRecord[]).filter((x) => x && typeof x === 'object') : []
}

const pages = computed<AnyRecord[]>(() => asRecords(detail.data.value?.original_result?.pages))
const totalPages = computed(() => Math.max(pages.value.length, 1))
const tableItems = computed<AnyRecord[]>(() => asRecords(detail.data.value?.original_result?.tables))

const currentPageRecord = computed<AnyRecord | undefined>(() =>
  pages.value.find((p) => Number(p.page ?? p.page_number ?? p.page_no ?? p.page_index) === currentPage.value)
    || (pages.value.length === 1 ? pages.value[0] : undefined)
)

const pageText = computed(() => {
  const hit = currentPageRecord.value
  if (hit) return String(hit.text ?? hit.raw_text ?? hit.content ?? hit.markdown ?? '')
  // 后端未按页切分时显示全文，并在关联条明确说明，不伪造分页
  return detail.data.value?.raw_text || ''
})

const pageLinkText = computed(() => {
  if (pages.value.length === 0) return '后端未提供按页结构，右侧显示完整 OCR 文本'
  return pageText.value ? pageText.value.slice(0, 60) + (pageText.value.length > 60 ? '…' : '') : '该页无文本字段'
})

const pageTableCount = computed(() => {
  const hit = currentPageRecord.value
  if (!hit) return 0
  const t = hit.tables ?? hit.table_count
  return Array.isArray(t) ? t.length : Number(t || 0)
})

const originalResultJson = computed(() =>
  detail.data.value ? JSON.stringify(detail.data.value.original_result, null, 2) : '〔暂无结果〕'
)

const qualityEntries = computed(() => {
  const q = detail.data.value?.quality
  if (!q || typeof q !== 'object') return []
  return Object.entries(q).map(([key, value]) => ({
    key,
    value: typeof value === 'object' ? JSON.stringify(value) : String(value ?? '—')
  }))
})

const reviewReason = computed(() => {
  const q = detail.data.value?.quality as AnyRecord | undefined
  const reason = q?.review_reason ?? q?.reason ?? q?.warnings
  if (reason) return `后端质量字段说明：${typeof reason === 'object' ? JSON.stringify(reason) : String(reason)}`
  return '后端未返回明确的人工复核原因字段；前端不推断、不编造理由，仅按 requires_review 标记展示。'
})

const expectedSha256 = computed(() => {
  const loc = detail.data.value?.source_location as AnyRecord | undefined
  const v = loc?.sha256 ?? loc?.file_sha256
  return typeof v === 'string' ? v : ''
})

function tableShape(t: AnyRecord): string {
  const rows = t.rows ?? t.row_count
  const cols = t.cols ?? t.column_count ?? t.columns
  if (Array.isArray(rows) && Array.isArray(cols)) return `${rows.length} 行 × ${cols.length} 列`
  if (rows != null && cols != null) return `${rows} 行 × ${cols} 列`
  return '结构字段见原文'
}

function formatTime(v: string) { return v ? String(v).replace('T', ' ').slice(0, 19) : '—' }
</script>

<style scoped>
.review-page { display: flex; flex-direction: column; height: calc(100vh - var(--mr-header-h)); overflow: hidden; }
.header-tags { display: flex; gap: 8px; align-items: center; }
.review-notice { margin-bottom: 12px; }
.queue-card { margin-bottom: 0; flex-shrink: 0; }
.queue-card.resizable { overflow-y: auto; }
.queue-card :deep(.el-card__body) { padding: 10px 14px; }
.card-head { display: flex; justify-content: space-between; align-items: center; font-weight: 600; }
.card-sub { font-weight: 400; font-size: 12px; color: var(--mr-text-3); }
.queue-pager { display: flex; justify-content: flex-end; margin-top: 8px; }
.review-split { flex: 1; display: grid; grid-template-columns: 1fr 1.2fr; gap: 16px; min-height: 0; }
.pane { min-height: 0; display: flex; flex-direction: column; }
.pane-toolbar { padding: 8px 14px; border-bottom: 1px solid var(--mr-line); display: flex; align-items: center; justify-content: space-between; gap: 10px; flex-shrink: 0; }
.pane-head-left { display: flex; align-items: center; gap: 10px; min-width: 0; }
.pane-title { font-weight: 600; flex-shrink: 0; }
.source-hint { font-size: 11px; color: var(--mr-text-3); font-family: monospace; }
.expand-btn { flex-shrink: 0; margin-left: 8px; }
.preview-body { flex: 1; min-height: 0; background: #eef1f6; }
/* AsyncPanel 根容器撑成 flex 列后，result-body 的滚动才真正生效，长 JSON 不会被裁掉 */
.pane :deep(.async-panel) { display: flex; flex-direction: column; flex: 1 1 auto; min-height: 0; }
.page-link {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  padding: 8px 14px; background: #eef4ff; border-bottom: 1px solid #d5e5ff;
  color: #1e40af; font-size: 12px; flex-shrink: 0;
}
.page-link-text { flex: 1; min-width: 200px; color: var(--mr-text-2); }
.page-link-tables { color: var(--mr-st-warning); }
.result-tabs { flex: 1; min-width: 0; }
.result-tabs :deep(.el-tabs__header) { margin: 0; }
.result-body { flex: 1; overflow-y: auto; padding: 14px; min-height: 0; }
.result-pre { font-family: var(--mr-font); font-size: 13px; line-height: 1.8; white-space: pre-wrap; word-break: break-word; margin: 0; max-width: 100%; }
.table-list { display: flex; flex-direction: column; gap: 12px; }
.table-item { border: 1px solid var(--mr-line); border-radius: 6px; padding: 10px; background: #fafbfe; }
.table-item-head { font-weight: 600; font-size: 13px; margin-bottom: 6px; }
.quality-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; }
.quality-item { display: flex; flex-direction: column; align-items: center; gap: 6px; padding: 14px 0; border: 1px solid var(--mr-line); border-radius: var(--mr-radius); background: #fafbfe; }
.quality-value { font-size: 22px; font-weight: 700; color: var(--mr-primary); }
.quality-label { font-size: 12px; color: var(--mr-text-2); }
.hint-text { font-size: 12px; color: var(--mr-text-2); line-height: 1.8; }
.meta-bar { display: flex; gap: 14px; padding: 10px 14px; border-top: 1px solid var(--mr-line); font-size: 12px; color: var(--mr-text-2); flex-wrap: wrap; flex-shrink: 0; }
.mono { font-family: monospace; font-size: 12px; }
.action-bar { display: flex; gap: 10px; padding: 12px 14px 4px; border-top: 1px solid var(--mr-line); background: #fafbfe; flex-wrap: wrap; flex-shrink: 0; }
.action-hint { padding: 0 14px 10px; background: #fafbfe; flex-shrink: 0; }

/* 上下拖动分隔条：只调整队列卡片高度，对比区自动拿剩余空间 */
.split-toolbar { display: flex; align-items: center; gap: 12px; flex-shrink: 0; margin: 8px 0; }
.v-resizer {
  flex: 1; min-width: 0; height: 20px; display: flex; align-items: center; justify-content: center; gap: 10px;
  cursor: row-resize; user-select: none; border: 1px solid var(--mr-line); border-radius: 4px;
  background: #f1f5fb; color: var(--mr-text-3); font-size: 11px;
}
.v-resizer:hover { background: #e3ecfa; color: var(--mr-primary); border-color: #b9cdf0; }
.v-resizer.disabled { cursor: default; }
.v-resizer-grip { letter-spacing: 2px; font-weight: 700; }
.both-expand-btn { flex-shrink: 0; }
/* 对照放大时工具条常驻顶部，保证「退出对照放大」始终可见可点 */
.split-toolbar.on-top {
  position: fixed; top: 0; left: 0; right: 0; z-index: 2002; margin: 0;
  padding: 8px 20px; box-sizing: border-box; background: #fff;
  border-bottom: 1px solid var(--mr-line); box-shadow: 0 2px 10px rgba(15, 43, 82, .12);
}

/* 滚动条滑块统一样式见 styles/index.css（七个页面全局生效） */

/* 放大查看：外层容器脱离栅格占满视口，内部仍是同一组件实例（PDF iframe 不重建） */
.pane-backdrop { position: fixed; inset: 0; z-index: 2000; background: rgba(15, 43, 82, .42); }
.pane.expanded {
  position: fixed; inset: 20px; z-index: 2001; margin: 0;
  display: flex; flex-direction: column;
  box-shadow: 0 18px 48px rgba(15, 43, 82, .3); border-radius: 8px;
}
.pane.expanded :deep(.el-card__body) { flex: 1 1 auto; min-height: 0; }
.pane.expanded .result-pre { font-size: 14px; line-height: 1.9; }

/* 对照放大：左右两栏同时占满视口并保持并排，原文与解析结果同屏对比 */
.review-split.expanded-both {
  position: fixed; inset: 52px 20px 20px; z-index: 2001; margin: 0; box-sizing: border-box;
  grid-template-columns: 1fr 1.2fr; gap: 16px;
  box-shadow: 0 18px 48px rgba(15, 43, 82, .3); border-radius: 8px;
  background: var(--mr-bg, #fff); padding: 8px;
}
.review-split.expanded-both .result-pre { font-size: 14px; line-height: 1.9; }
@media (max-width: 768px) {
  .pane.expanded { inset: 8px; }
  .review-split.expanded-both { inset: 44px 8px 8px; gap: 8px; padding: 4px; grid-template-columns: 1fr 1fr; }
}
@media (max-width: 1366px) {
  .review-split { grid-template-columns: 1fr 1fr; }
  .quality-grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 1280px) {
  .review-split { grid-template-columns: 1fr; overflow-y: auto; }
}

/* 审核台账与写入弹窗 */
.ledger-summary { display: flex; gap: 14px; flex-wrap: wrap; align-items: center; margin-bottom: 12px; font-size: 12px; color: var(--mr-text-2); }
.revision-box { margin-top: 12px; border: 1px solid var(--mr-line); border-radius: 6px; padding: 10px; background: #fafbfe; }
.revision-head { font-weight: 600; font-size: 12px; margin-bottom: 8px; }
.action-form .form-hint { margin-left: 10px; font-size: 12px; color: var(--mr-text-3); }
</style>
