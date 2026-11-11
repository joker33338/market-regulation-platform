<template>
  <div class="page review-page">
    <div class="page-header">
      <div>
        <h1 class="page-title">文档审核中心</h1>
        <p class="page-desc">解析结果人工复核 —— 原始解析结果只读，人工修订须留痕，不得覆盖原始证据文件</p>
      </div>
      <div style="display: flex; gap: 8px; align-items: center">
        <el-tag type="warning" effect="plain">审核写入接口未接入 · 只读</el-tag>
        <DemoBadge />
      </div>
    </div>

    <el-alert
      type="warning"
      :closable="false"
      class="review-notice"
      title="当前为只读预览，所有审核写操作已禁用"
      description="后端 qa_core/indexing/ocr_review.py 仅有服务层，无审核读写 HTTP 接口；原始文件读取接口亦未接入。左侧不渲染模拟页面、不用 artifact.bin 冒充原始证据、不提供本地选文件预览；右侧解析结果为 DEMO 占位文本，不含任何法规原文。"
    />

    <!-- 待审核队列（DEMO） -->
    <el-card shadow="never" style="margin-bottom: 16px">
      <div class="queue-bar">
        <span class="queue-label">待审核队列 <DemoBadge />：</span>
        <el-tag v-for="d in queueList" :key="d" :type="d === activeQueue ? 'primary' : 'info'" effect="plain"
          style="cursor: pointer; margin-right: 8px" @click="activeQueue = d">{{ d }}</el-tag>
        <span class="queue-count num">共 {{ queueList.length }} 份</span>
      </div>
    </el-card>

    <div class="review-split">
      <!-- 左：原始文件预览（唯一文件源为后端接口适配层） -->
      <el-card shadow="never" class="pane" :body-style="{ padding: 0, height: '100%', display: 'flex', flexDirection: 'column' }">
        <div class="pane-toolbar">
          <span class="pane-title">原始文件预览</span>
          <span class="source-hint">文件源：{{ SOURCE_FILE_API }}</span>
        </div>
        <div class="preview-body">
          <DocumentPreview :file-id="doc.docId" v-model:page="currentPage" :total-pages="doc.pages" />
        </div>
      </el-card>

      <!-- 右：解析结果，与左侧共享 currentPage -->
      <el-card shadow="never" class="pane" :body-style="{ padding: 0, height: '100%', display: 'flex', flexDirection: 'column' }">
        <div class="pane-toolbar">
          <el-tabs v-model="resultTab" class="result-tabs">
            <el-tab-pane label="OCR 文本" name="text" />
            <el-tab-pane label="Markdown" name="markdown" />
            <el-tab-pane label="JSON" name="json" />
            <el-tab-pane label="表格结构" name="table" />
            <el-tab-pane label="质量指标" name="quality" />
          </el-tabs>
        </div>

        <!-- 按页关联：左侧翻页时右侧同步定位到该页解析结果 -->
        <div class="page-link">
          <el-icon><Connection /></el-icon>
          <span>按页对照 · 当前第 <b class="num">{{ currentPage }}</b> 页：</span>
          <span class="page-link-text">{{ pageResult.text }}</span>
          <span v-if="pageResult.tables" class="page-link-tables num">含 {{ pageResult.tables }} 个表格</span>
          <DemoBadge />
        </div>

        <div class="result-body">
          <pre v-if="resultTab === 'text'" class="result-pre">{{ pageResult.text }}</pre>
          <pre v-else-if="resultTab === 'markdown'" class="result-pre">{{ doc.markdown }}</pre>
          <pre v-else-if="resultTab === 'json'" class="result-pre">{{ doc.jsonResult }}</pre>
          <div v-else-if="resultTab === 'table'" class="table-pane">
            <el-alert type="info" :closable="false" title="表格结构为 DEMO 占位数据，真实结构来自后端 results 接口" style="margin-bottom: 12px" />
            <el-table :data="tableRows" border size="small">
              <el-table-column prop="no" label="序号" width="70" />
              <el-table-column prop="location" label="位置" width="100" />
              <el-table-column prop="shape" label="结构" width="110" />
              <el-table-column label="置信度" width="110">
                <template #default="{ row }">
                  <span class="num" :style="{ color: row.confidence >= 0.9 ? 'var(--mr-st-success)' : 'var(--mr-st-warning)' }">
                    {{ (row.confidence * 100).toFixed(1) }}%
                  </span>
                </template>
              </el-table-column>
              <el-table-column prop="note" label="备注" />
            </el-table>
          </div>
          <div v-else class="quality-pane">
            <div class="quality-grid">
              <div class="quality-item"><span class="num quality-value">{{ (doc.confidence * 100).toFixed(1) }}%</span><span class="quality-label">整体置信度</span></div>
              <div class="quality-item"><span class="num quality-value">{{ doc.tableCount }}</span><span class="quality-label">识别表格数</span></div>
              <div class="quality-item"><span class="num quality-value">{{ doc.charCount.toLocaleString() }}</span><span class="quality-label">识别字符数</span></div>
              <div class="quality-item"><span class="num quality-value">{{ doc.pages }}</span><span class="quality-label">页数</span></div>
            </div>
          </div>
        </div>

        <div class="meta-bar">
          <span>引擎：<b>{{ doc.engine }}</b>（DEMO）</span>
          <span>解析时间：{{ doc.parsedAt }}</span>
          <span>结果来源：解析结果接口未接入</span>
          <el-tooltip :content="doc.sha256">
            <span class="sha-short">SHA256（DEMO）: {{ doc.sha256.slice(0, 16) }}…</span>
          </el-tooltip>
        </div>

        <!-- 底部操作：接口未接入 → 全部 disabled，不出现假装成功 -->
        <div class="action-bar">
          <el-tooltip v-for="a in actions" :key="a" :content="disabledHint" placement="top">
            <span><el-button :type="a === '审核通过' ? 'success' : a === '退回重新解析' ? 'warning' : a === '标记识别错误' ? 'danger' : 'primary'" disabled>{{ a }}</el-button></span>
          </el-tooltip>
        </div>
        <div class="action-hint mr-disabled-hint">{{ disabledHint }}</div>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Connection } from '@element-plus/icons-vue'
import DemoBadge from '@/components/DemoBadge.vue'
import DocumentPreview from '@/components/document/DocumentPreview.vue'
import { SOURCE_FILE_API } from '@/api/documentFiles'
import { apiCapabilities, unimplementedHint } from '@/api/dataSource'
import { fetchReviewDoc, type ReviewItem } from '@/api/mock/review'

const REVIEW_WRITE_API = 'GET /api/review/{doc_id} + POST /api/review/{doc_id}/approve|reject|mark-error|save-revision'
const disabledHint = apiCapabilities.reviewWrite
  ? '审核写入接口已交付，等待前端适配层启用'
  : unimplementedHint(REVIEW_WRITE_API)

const actions = ['审核通过', '退回重新解析', '标记识别错误', '保存人工修订']

const doc = ref<ReviewItem>({
  docId: '', fileName: '', sha256: '', engine: '', parsedAt: '',
  pages: 1, confidence: 0, tableCount: 0, charCount: 0,
  markdown: '', jsonResult: '', pagesResult: []
})
const currentPage = ref(1)
const resultTab = ref('markdown')
const activeQueue = ref('市场监督管理行政处罚程序规定.pdf')
const queueList = ref([
  '市场监督管理行政处罚程序规定.pdf',
  '广告绝对化用语执法指南.pdf',
  '检验检测机构监督管理办法.pdf'
])

const tableRows = ref([
  { no: 'T-01', location: '第 5 页', shape: '8 行 × 4 列', confidence: 0.96, note: '结构占位' },
  { no: 'T-02', location: '第 7 页', shape: '12 行 × 3 列', confidence: 0.88, note: '结构占位' },
  { no: 'T-03', location: '第 12 页', shape: '6 行 × 5 列', confidence: 0.91, note: '结构占位' }
])

/** 左右共享页码：右侧按页定位解析结果 */
const pageResult = computed(() =>
  doc.value.pagesResult.find((p) => p.page === currentPage.value) ?? {
    page: currentPage.value,
    text: '〔该页暂无 DEMO 解析结果〕',
    tables: 0
  }
)

onMounted(async () => {
  const { data } = await fetchReviewDoc()
  doc.value = data
})
</script>

<style scoped>
.review-page { display: flex; flex-direction: column; height: calc(100vh - var(--mr-header-h)); overflow: hidden; }
.review-notice { margin-bottom: 14px; }
.queue-bar { display: flex; align-items: center; flex-wrap: wrap; }
.queue-label { color: var(--mr-text-2); font-size: 13px; margin-right: 4px; display: inline-flex; align-items: center; gap: 6px; }
.queue-count { margin-left: auto; color: var(--mr-text-3); font-size: 13px; }
.review-split { flex: 1; display: grid; grid-template-columns: 1fr 1.2fr; gap: 16px; min-height: 0; }
.pane { min-height: 0; }
.pane-toolbar { padding: 10px 14px; border-bottom: 1px solid var(--mr-line); display: flex; align-items: center; justify-content: space-between; }
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
.result-pre { font-family: var(--mr-font); font-size: 13px; line-height: 1.8; white-space: pre-wrap; word-break: break-word; margin: 0; max-width: 72ch; }
.quality-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; }
.quality-item { display: flex; flex-direction: column; align-items: center; gap: 6px; padding: 18px 0; border: 1px solid var(--mr-line); border-radius: var(--mr-radius); background: #fafbfe; }
.quality-value { font-size: 24px; font-weight: 700; color: var(--mr-primary); }
.quality-label { font-size: 12px; color: var(--mr-text-2); }
.meta-bar { display: flex; gap: 18px; padding: 10px 14px; border-top: 1px solid var(--mr-line); font-size: 12px; color: var(--mr-text-2); flex-wrap: wrap; }
.sha-short { font-family: monospace; cursor: help; }
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
