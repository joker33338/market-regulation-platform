<template>
  <div class="page review-page">
    <div class="page-header">
      <div>
        <h1 class="page-title">文档审核中心</h1>
        <p class="page-desc">解析结果人工复核 —— 原始解析结果只读，人工修订须留痕，不得覆盖原始证据文件</p>
      </div>
      <div class="header-tags">
        <el-tag type="danger" effect="plain">正式审核写入未实现 · 只读</el-tag>
        <el-tag :type="contractState === 'ready' ? 'success' : 'warning'" effect="plain">{{ contractLabel[contractState] }}</el-tag>
      </div>
    </div>

    <el-alert type="warning" :closable="false" class="review-notice"
      title="当前为只读审核预览，四个审核写操作全部禁用"
      description="待复核队列来自 GET /api/review（document_review.documents 完整语义，不依赖 findings 级 v_review_queue 视图）；详情来自 GET /api/review/{parse_id}；左侧原件来自 owner 隔离的 /source 接口。后端 review_write_supported 恒为 false，且未提供任何审核写入 HTTP 接口，前端不做本地状态变更、不假装审核成功。Markdown / 表格内容按纯文本展示，不执行 HTML。" />

    <!-- 待复核队列：真实完整语义接口 -->
    <el-card shadow="never" class="queue-card">
      <template #header>
        <div class="card-head">
          <span>待复核队列 <span class="real-badge">REAL</span></span>
          <span class="card-sub">GET /api/review?requires_review=true · 数据源 document_review.documents</span>
        </div>
      </template>
      <AsyncPanel :state="queue.state.value" :error="queue.error.value" empty-text="当前没有待人工复核的文档（后端返回空列表）" @retry="queue.load()">
        <el-table :data="queue.data.value?.list || []" size="small" highlight-current-row @current-change="onSelectQueue">
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

    <!-- 左右双栏 -->
    <div class="review-split">
      <el-card shadow="never" class="pane" :body-style="{ padding: 0, height: '100%', display: 'flex', flexDirection: 'column' }">
        <div class="pane-toolbar">
          <span class="pane-title">原始文件预览</span>
          <span class="source-hint">GET /api/parse/files/{source_file_id}/source</span>
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

      <el-card shadow="never" class="pane" :body-style="{ padding: 0, height: '100%', display: 'flex', flexDirection: 'column' }">
        <div class="pane-toolbar">
          <el-tabs v-model="resultTab" class="result-tabs">
            <el-tab-pane label="OCR 文本" name="text" />
            <el-tab-pane label="Markdown" name="markdown" />
            <el-tab-pane label="JSON" name="json" />
            <el-tab-pane label="表格结构" name="table" />
            <el-tab-pane label="质量指标" name="quality" />
            <el-tab-pane label="候选对照" name="candidate" />
          </el-tabs>
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
          </div>
        </AsyncPanel>

        <!-- 底部操作：后端无写入接口 → 全部禁用，绝不假装成功 -->
        <div class="action-bar">
          <el-tooltip v-for="a in actions" :key="a.label" :content="disabledHint" placement="top">
            <span><el-button :type="a.type" disabled>{{ a.label }}</el-button></span>
          </el-tooltip>
        </div>
        <div class="action-hint mr-disabled-hint">{{ disabledHint }}</div>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { Connection } from '@element-plus/icons-vue'
import AsyncPanel from '@/components/AsyncPanel.vue'
import DocumentPreview from '@/components/document/DocumentPreview.vue'
import { useAsyncData } from '@/composables/useAsyncData'
import { listReviews, getReviewDetail } from '@/api/frontend'
import { contractState, contractLabel, unimplementedHint } from '@/api/dataSource'
import type { ReviewDetail, ReviewQueue, ReviewQueueItem } from '@/api/types'

/**
 * v0.2.2 审核中心：
 * - 队列 = GET /api/review（完整语义，后端读 document_review.documents，不依赖 v_review_queue）
 * - 详情 = GET /api/review/{parse_id}（raw_text / markdown / original_result / quality / 候选对照）
 * - 原件 = /source 授权字节，SHA256 由后端 X-SHA256 校验
 * - 写操作：后端契约 review_write_supported=false 且无 HTTP 接口 → 全部禁用
 * - Markdown / 表格一律纯文本，不使用 v-html，不执行不可信 HTML
 */
const REVIEW_WRITE_AVAILABLE = false // 后端未提供写入 API，前端无写入适配层；不得改为 true

const queuePage = ref(1)
const queuePageSize = 10
const currentParseId = ref('')
const currentPage = ref(1)
const resultTab = ref('text')

const queue = useAsyncData<ReviewQueue>(
  (signal) => listReviews({ page: queuePage.value, pageSize: queuePageSize, requiresReview: true }, signal)
)
const detail = useAsyncData<ReviewDetail>(
  (signal) => getReviewDetail(currentParseId.value, signal),
  { immediate: false, isEmpty: () => false }
)
// 尚未选择队列记录时显示明确空态，而非无限 loading
detail.state.value = 'empty'

const actions = [
  { label: '审核通过', type: 'success' },
  { label: '退回重新解析', type: 'warning' },
  { label: '标记识别错误', type: 'danger' },
  { label: '保存人工修订', type: 'primary' }
] as const

const disabledHint = REVIEW_WRITE_AVAILABLE
  ? ''
  : unimplementedHint('POST /api/review/{parse_id}/approve | reject | mark-error | save-revision') +
    '；后端 review_write_supported 恒为 false，且需保留原始解析结果与审计留痕'

function onSelectQueue(row: ReviewQueueItem | null) {
  if (!row?.parse_id) return
  currentParseId.value = row.parse_id
  currentPage.value = 1
  resultTab.value = 'text'
  void detail.load()
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
.queue-card { margin-bottom: 14px; flex-shrink: 0; }
.queue-card :deep(.el-card__body) { padding: 10px 14px; }
.card-head { display: flex; justify-content: space-between; align-items: center; font-weight: 600; }
.card-sub { font-weight: 400; font-size: 12px; color: var(--mr-text-3); }
.queue-pager { display: flex; justify-content: flex-end; margin-top: 8px; }
.review-split { flex: 1; display: grid; grid-template-columns: 1fr 1.2fr; gap: 16px; min-height: 0; }
.pane { min-height: 0; }
.pane-toolbar { padding: 8px 14px; border-bottom: 1px solid var(--mr-line); display: flex; align-items: center; justify-content: space-between; }
.pane-title { font-weight: 600; }
.source-hint { font-size: 11px; color: var(--mr-text-3); font-family: monospace; }
.preview-body { flex: 1; min-height: 0; background: #eef1f6; }
.page-link {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  padding: 8px 14px; background: #eef4ff; border-bottom: 1px solid #d5e5ff;
  color: #1e40af; font-size: 12px;
}
.page-link-text { flex: 1; min-width: 200px; color: var(--mr-text-2); }
.page-link-tables { color: var(--mr-st-warning); }
.result-tabs { width: 100%; }
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
.meta-bar { display: flex; gap: 14px; padding: 10px 14px; border-top: 1px solid var(--mr-line); font-size: 12px; color: var(--mr-text-2); flex-wrap: wrap; }
.mono { font-family: monospace; font-size: 12px; }
.action-bar { display: flex; gap: 10px; padding: 12px 14px 4px; border-top: 1px solid var(--mr-line); background: #fafbfe; flex-wrap: wrap; }
.action-hint { padding: 0 14px 10px; background: #fafbfe; }
@media (max-width: 1366px) {
  .review-split { grid-template-columns: 1fr 1fr; }
  .quality-grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 1280px) {
  .review-split { grid-template-columns: 1fr; overflow-y: auto; }
}
</style>
