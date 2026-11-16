<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h1 class="page-title">知识库入库管理</h1>
        <p class="page-desc">Chunk 结构预览 · public 版本只读查询 · draft-4 入库链路按运行期方法级门控接入</p>
      </div>
      <div class="header-tags">
        <el-tag type="success" effect="plain">真实接口 /api/knowledge/versions</el-tag>
        <el-tag :type="contractState === 'ready' ? 'success' : 'warning'" effect="plain">{{ contractLabel[contractState] }}</el-tag>
        <el-tooltip :content="writeGateHint" placement="top">
          <span><el-button type="primary" :disabled="!canCreateBatch" @click="scrollToWrite">发起入库批次</el-button></span>
        </el-tooltip>
      </div>
    </div>

    <!-- 边界：预览恒只读；写链路按运行期契约 + ADMIN + 能力声明三重门控 -->
    <el-alert
      type="warning"
      :closable="false"
      class="readonly-notice"
      :title="ingestionAlertTitle"
      :description="ingestionAlertDescription" />
    <div class="mr-disabled-hint" style="margin-bottom: 12px">{{ writeGateHint }}</div>

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
        <div class="version-filters" role="group" aria-label="知识库版本筛选">
          <el-input v-model="versionKeyword" aria-label="版本号关键词" placeholder="搜索版本号" clearable />
          <el-select v-model="versionStatus" aria-label="版本状态" placeholder="全部状态" clearable><el-option v-for="status in versionStatuses" :key="status" :label="status" :value="status" /></el-select>
          <el-checkbox v-model="versionActiveOnly">仅当前生效</el-checkbox>
          <el-button @click="resetVersionFilters">重置筛选</el-button>
          <el-button :loading="versions.loading.value" @click="versions.load()">刷新版本</el-button>
        </div>
        <p v-if="versions.data.value" class="filter-feedback" role="status">已完整加载 {{ versions.data.value?.total ?? 0 }} 个可见版本，符合条件 {{ filteredVersions.length }} 个。筛选作用于全部已加载版本。</p>
        <AsyncPanel :state="versions.state.value" :error="versions.error.value" empty-text="public 知识库暂无版本记录（后端返回空列表）" @retry="versions.load()">
          <el-table :data="visibleVersions" size="small" highlight-current-row max-height="260" @current-change="onSelectVersion">
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
          <el-empty v-if="filteredVersions.length === 0" :image-size="54" description="没有符合条件的版本"><el-button @click="resetVersionFilters">清空版本筛选</el-button></el-empty>
          <div class="queue-pager">
            <el-pagination v-model:current-page="versionPage" :page-size="versionPageSize" :total="filteredVersions.length"
              layout="total, prev, pager, next" small background />
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

    <!-- ③ draft-4 正式入库链路：预检 / 批次 / 版本校验 / 发布 / 回滚 / 批次历史 -->
    <el-card id="ingestion-write" shadow="never" style="margin-top: 16px">
      <template #header>
        <div class="card-head">
          <span>正式入库链路（draft-4）<span class="real-badge">REAL</span></span>
          <span class="card-sub">运行期方法级门控 · ADMIN 逐请求授权 · 写接口必带 Idempotency-Key</span>
        </div>
      </template>

      <el-alert type="warning" :closable="false" style="margin-bottom: 10px"
        title="写入边界"
        description="预检与版本校验是只读语义的 POST（write_performed=false）；批次、发布、回滚仅 ADMIN 可执行，创建批次返回 201 STAGED 且不自动发布。发布/回滚必填 expected_active_version（初次发布为 null），不一致由后端 409 拒绝。本地 4173 预览的默认代理会拦截所有非 GET 请求（frontend_write_guard），需指向经授权的隔离入口才能联通；403 时如实显示错误态，不伪造成功。" />
      <div class="mr-disabled-hint" style="margin-bottom: 10px">{{ ingestionCapabilityHint }}</div>

      <div class="ingest-form">
        <el-input v-model="batchKbVersion" placeholder="目标 kb_version（必填）" clearable style="width: 240px" />
        <el-switch v-model="fullSnapshot" active-text="full_snapshot" inactive-text="增量" />
        <el-input v-model="docsJson" type="textarea" :rows="3" style="width: 100%"
          placeholder='documents JSON 数组：[{"parse_id":"...","law_name":"...","law_id":"...","expected_review_version":1}]' />
      </div>
      <div class="mr-disabled-hint" style="margin: 6px 0 10px">
        documents 只能取自后端已持久化的解析结果，前端不拼接推导；请求体遵循 additionalProperties=false。
        有 current_revision 且人工修订导出协议未确认时，后端返回 409 reviewed_revision_export_required，页面不把旧 OCR 当作已修订正文。
      </div>
      <div class="action-row">
        <el-button size="small" :disabled="!canPrecheck" :loading="precheck.loading.value" @click="runPrecheck">预检（只读）</el-button>
        <el-button type="primary" size="small" :disabled="!canCreateBatch" :loading="batchBusy" @click="runCreateBatch">发起入库批次</el-button>
        <span class="mr-disabled-hint">幂等键：{{ batchIdempotencyKey || '（提交时生成；结果未确认的重试沿用同键）' }}</span>
      </div>

      <AsyncPanel :state="precheck.state.value" :error="precheck.error.value" @retry="runPrecheck">
        <template #empty><el-empty :image-size="54" description="尚未预检：填写 kb_version 与 documents 后点击「预检（只读）」" /></template>
        <el-descriptions v-if="precheck.data.value" :column="3" border size="small" style="margin-top: 10px">
          <el-descriptions-item label="eligible">{{ precheck.data.value.eligible }}</el-descriptions-item>
          <el-descriptions-item label="active_version">{{ precheck.data.value.active_version || '—' }}</el-descriptions-item>
          <el-descriptions-item label="target_exists">{{ precheck.data.value.target_exists }}</el-descriptions-item>
          <el-descriptions-item label="write_performed">{{ precheck.data.value.write_performed }}</el-descriptions-item>
          <el-descriptions-item label="publish_authorized">{{ precheck.data.value.publish_authorized }}</el-descriptions-item>
          <el-descriptions-item label="逐项数">{{ precheck.data.value.documents.length }}</el-descriptions-item>
        </el-descriptions>
        <el-table v-if="precheck.data.value?.documents.length" :data="precheck.data.value.documents" size="small" max-height="220" style="margin-top: 8px">
          <el-table-column prop="parse_id" label="parse_id" min-width="180" show-overflow-tooltip />
          <el-table-column prop="review_version" label="review_version" width="140" />
          <el-table-column prop="chunk_count" label="chunk_count" width="120" align="right" />
          <el-table-column label="quality_passed" width="130"><template #default="{ row }">{{ row.quality_passed ?? '—' }}</template></el-table-column>
          <el-table-column label="eligible" width="100"><template #default="{ row }"><el-tag size="small" :type="row.eligible ? 'success' : 'danger'" effect="plain">{{ row.eligible }}</el-tag></template></el-table-column>
          <el-table-column prop="error_code" label="error_code" min-width="180" show-overflow-tooltip />
        </el-table>
      </AsyncPanel>

      <div v-if="batchReceipt" class="receipt-box">
        <div class="card-head"><span>批次回执（后端真实响应）</span><span class="card-sub">outcome_unconfirmed 时必须同键重试核对，不能当成失败或成功</span></div>
        <pre class="result-pre">{{ asJson(batchReceipt) }}</pre>
      </div>

      <el-divider content-position="left">版本校验 / 发布 / 回滚</el-divider>
      <div class="action-row">
        <el-input v-model="releaseKbVersion" placeholder="kb_version（发布 / 校验目标）" clearable style="width: 250px" />
        <el-input v-model="expectedActive" placeholder="expected_active_version（初次发布留空 = null）" clearable style="width: 300px" />
        <el-button size="small" :disabled="!canVersionCheck" :loading="versionCheck.loading.value" @click="runVersionCheck">版本校验（只读）</el-button>
        <el-button size="small" :disabled="!canRelease('publish')" :loading="releaseBusy" @click="runRelease('publish')">发布 ACTIVE</el-button>
        <el-button size="small" :disabled="!canRelease('rollback')" :loading="releaseBusy" @click="runRelease('rollback')">回滚</el-button>
      </div>
      <AsyncPanel :state="versionCheck.state.value" :error="versionCheck.error.value" @retry="runVersionCheck">
        <template #empty><el-empty :image-size="54" description="尚未校验：填写 kb_version 后点击「版本校验（只读）」" /></template>
        <el-descriptions v-if="versionCheck.data.value" :column="3" border size="small" style="margin-top: 10px">
          <el-descriptions-item label="kb_version">{{ versionCheck.data.value.kb_version }}</el-descriptions-item>
          <el-descriptions-item label="status">{{ versionCheck.data.value.status }}</el-descriptions-item>
          <el-descriptions-item label="is_active">{{ versionCheck.data.value.is_active }}</el-descriptions-item>
          <el-descriptions-item label="base_version">{{ versionCheck.data.value.base_version || '—' }}</el-descriptions-item>
          <el-descriptions-item label="active_version">{{ versionCheck.data.value.active_version || '—' }}</el-descriptions-item>
          <el-descriptions-item label="base_matches_active">{{ versionCheck.data.value.base_matches_active }}</el-descriptions-item>
          <el-descriptions-item label="publish_eligible">{{ versionCheck.data.value.publish_eligible }}</el-descriptions-item>
          <el-descriptions-item label="rollback_eligible">{{ versionCheck.data.value.rollback_eligible }}</el-descriptions-item>
          <el-descriptions-item label="write_performed">{{ versionCheck.data.value.write_performed }}</el-descriptions-item>
        </el-descriptions>
        <div class="mr-disabled-hint" style="margin-top: 6px">技术条件 eligible ≠ 已获发布授权；publish_authorized 与后端逐请求授权为准。</div>
      </AsyncPanel>
      <div v-if="releaseReceipt" class="receipt-box">
        <div class="card-head"><span>发布 / 回滚回执（后端真实响应）</span><span class="card-sub">成功后仍须重新查询当前 ACTIVE，历史回执不等于当前指针</span></div>
        <pre class="result-pre">{{ asJson(releaseReceipt) }}</pre>
      </div>

      <el-divider content-position="left">批次历史 · GET /api/ingestion/batches</el-divider>
      <div class="action-row">
        <el-button size="small" :disabled="!routeBatchesGet" @click="batches.load()">刷新批次</el-button>
        <span class="mr-disabled-hint">{{ routeBatchesGet ? 'ADMIN 查看全部批次，其他身份仅本人历史（以响应为准）' : '运行期未加载该接口，保持空态' }}</span>
      </div>
      <el-empty v-if="!routeBatchesGet" :image-size="54" description="运行期未加载 GET /api/ingestion/batches，不展示演示批次" />
      <AsyncPanel v-else :state="batches.state.value" :error="batches.error.value" empty-text="暂无真实入库批次记录" @retry="batches.load()">
        <el-table :data="batches.data.value?.list || []" size="small" max-height="220" highlight-current-row @current-change="selectBatch">
          <el-table-column prop="operation_id" label="operation_id" min-width="180" show-overflow-tooltip />
          <el-table-column prop="action" label="action" width="140" />
          <el-table-column prop="kb_version" label="kb_version" min-width="160" show-overflow-tooltip />
          <el-table-column prop="status" label="status" width="130" />
          <el-table-column label="time" width="180"><template #default="{ row }">{{ formatTime(row.created_at) }}</template></el-table-column>
        </el-table>
      </AsyncPanel>
      <div v-if="batchDetail" class="receipt-box">
        <div class="card-head"><span>批次详情回执</span><span class="card-sub">execution_live / outcome_unconfirmed 如实展示</span></div>
        <pre class="result-pre">{{ asJson(batchDetail) }}</pre>
      </div>
    </el-card>

    <!-- ④ 运行期入库能力状态：不再写死「未实现」结论 -->
    <el-card shadow="never" style="margin-top: 16px">
      <template #header>
        <div class="card-head">
          <span>运行期入库能力状态</span>
          <span class="card-sub">以 GET /api/openapi.json 方法级探测为准 · {{ contractLabel[contractState] }}</span>
        </div>
      </template>
      <el-table :data="INGESTION_ROUTES" size="small">
        <el-table-column prop="method" label="方法" width="90" />
        <el-table-column prop="path" label="路径" min-width="300" show-overflow-tooltip />
        <el-table-column prop="usage" label="对应业务" min-width="200" show-overflow-tooltip />
        <el-table-column label="运行期" width="110">
          <template #default="{ row }">
            <span :class="runtimeHas(row.method, row.path) ? 'run-ready' : 'run-pending'">
              {{ runtimeHas(row.method, row.path) ? '已加载' : '未加载' }}
            </span>
          </template>
        </el-table-column>
      </el-table>
      <div class="mr-disabled-hint" style="margin-top: 10px">
        源码契约已交付 ≠ 活动实例已加载；未加载的路由对应按钮一律禁用 / 空态，不调用不存在的接口。
        七阶段流水线、批次四态、法规数据表仍无真实 HTTP 数据源，不以 DEMO 形式呈现；
        写操作另需 ADMIN 身份、后端逐请求授权与 write_configured，任一项不满足均如实报错，不做本地假成功。
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useRoute } from 'vue-router'
import AsyncPanel from '@/components/AsyncPanel.vue'
import { useAsyncData } from '@/composables/useAsyncData'
import {
  previewTaskFile, previewReviewResult, listAllKbVersions, getKbVersion
} from '@/api/frontend'
import {
  contractState, contractLabel, hasRuntimeMethod
} from '@/api/dataSource'
import { notifyApiError } from '@/api/errors'
import { isAdminIdentity } from '@/api/principal'
import {
  loadCapabilities, runtimeCapabilities, capabilitiesState,
  ingestionPrecheck, createIngestionBatch, listIngestionBatches, getIngestionBatch,
  ingestionVersionCheck, publishKbVersion, rollbackKbVersion
} from '@/api/ops'
import type {
  PreviewResponse, PreviewRequest, KbVersionList, VersionInfo, KbVersionItem,
  IngestionBatchRequest, IngestionDocument, PrecheckResponse, VersionCheckResponse,
  KnowledgeOperation, KnowledgeOperationPage
} from '@/api/types'

/**
 * v0.2.2 入库管理 / v0.2.3 draft-4 入库链路
 * - 预览 = 两个真实 POST，write_performed 恒 false；409 门禁失败按错误态呈现，不渲染空结构
 * - 版本 = GET /api/knowledge/versions + /{version}，只读 public，绝不读 mvp_test_*
 * - 写链路（precheck / batches / version-check / publish / rollback）按运行期方法级门控 + ADMIN +
 *   write_configured 三重收紧；未加载路由一律禁用 / 空态，不调用不存在的接口
 * - 写接口必带 Idempotency-Key：结果未确认（503 / 网络不明 / outcome_unconfirmed）沿用同键重试，
 *   仅结果确认后换键；403 / 409 / 503 不本地假成功、不移除已有记录
 * - 身份 ID 从后端 file_mappings / 解析历史 / 审核队列取得；解析中心通过 ?task=&file= 跳转回填
 */
const route = useRoute()

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
  (signal) => listAllKbVersions(signal)
)
const versionKeyword = ref('')
const versionStatus = ref('')
const versionActiveOnly = ref(false)
const filteredVersions = computed(() => (versions.data.value?.list || []).filter(row =>
  (!versionKeyword.value.trim() || row.kb_version.toLowerCase().includes(versionKeyword.value.trim().toLowerCase())) &&
  (!versionStatus.value || row.status === versionStatus.value) && (!versionActiveOnly.value || row.active)
))
const visibleVersions = computed(() => filteredVersions.value.slice((versionPage.value - 1) * versionPageSize, versionPage.value * versionPageSize))
const versionStatuses = computed(() => [...new Set((versions.data.value?.list || []).map(row => row.status))])
watch([versionKeyword, versionStatus, versionActiveOnly], () => { versionPage.value = 1 })
watch(() => versions.data.value, () => { versionPage.value = 1 })
function resetVersionFilters() { versionKeyword.value = ''; versionStatus.value = ''; versionActiveOnly.value = false; versionPage.value = 1 }
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

/* ───────── draft-4 正式入库链路 ───────── */
interface RouteRow { method: string; path: string; usage: string }
const INGESTION_ROUTES: RouteRow[] = [
  { method: 'POST', path: '/api/ingestion/precheck', usage: '逐项只读预检（eligible / error_code）' },
  { method: 'POST', path: '/api/ingestion/batches', usage: '创建入库批次（ADMIN + 幂等键，STAGED 不自动发布）' },
  { method: 'GET', path: '/api/ingestion/batches', usage: '批次历史（ADMIN 全局 / 其他仅本人）' },
  { method: 'GET', path: '/api/ingestion/batches/{batch_id}', usage: '批次回执详情（execution_live / outcome_unconfirmed）' },
  { method: 'GET', path: '/api/ingestion/version-check', usage: '只读版本技术条件校验' },
  { method: 'POST', path: '/api/ingestion/publish', usage: '发布 ACTIVE（expected_active_version + 幂等键）' },
  { method: 'POST', path: '/api/ingestion/rollback', usage: '回滚至 ARCHIVED（同上）' }
]
function runtimeHas(method: string, path: string): boolean {
  return hasRuntimeMethod(method, path)
}
const routePrecheck = computed(() => runtimeHas('POST', '/api/ingestion/precheck'))
const routeBatchesPost = computed(() => runtimeHas('POST', '/api/ingestion/batches'))
const routeBatchesGet = computed(() => runtimeHas('GET', '/api/ingestion/batches'))
const routeBatchGet = computed(() => runtimeHas('GET', '/api/ingestion/batches/{batch_id}'))
const routeVersionCheck = computed(() => runtimeHas('GET', '/api/ingestion/version-check'))
const routePublish = computed(() => runtimeHas('POST', '/api/ingestion/publish'))
const routeRollback = computed(() => runtimeHas('POST', '/api/ingestion/rollback'))

/** 后端能力声明：write_configured=false 时提交会 503，前端按真实配置收紧 */
const writeConfigured = computed(() => runtimeCapabilities.value?.ingestion?.write_configured !== false)
const adminReady = computed(() => isAdminIdentity.value)

const writeGateReady = computed(() =>
  contractState.value === 'ready' && routeBatchesPost.value && adminReady.value && writeConfigured.value
)
const writeGateHint = computed(() => {
  if (contractState.value !== 'ready') return '运行期契约未就绪：入库写路由尚未探测，按钮保持禁用'
  if (!routeBatchesPost.value) return '运行期 GET /api/openapi.json 未返回 POST /api/ingestion/batches，按钮保持禁用'
  if (!adminReady.value) return '当前身份非 ADMIN（或身份未确认）：入库批次仅 ADMIN 可创建，按后端逐请求授权为准'
  if (!writeConfigured.value) return '后端 ingestion.write_configured=false：独立入库写库未配置，提交会返回 503'
  return '方法级门控 + ADMIN 身份 + write_configured 均已满足；提交仍由后端逐请求校验，前端不预判成功'
})

const ingestionAlertTitle = computed(() =>
  writeGateReady.value ? '写链路已按运行期契约解锁（仍需后端逐请求授权）' : '写链路按运行期契约保持禁用'
)
const ingestionAlertDescription = computed(() =>
  '预览与版本列表恒只读：预览返回 write_performed=false，门禁失败为 409 且不是空成功；版本列表只读 public schema，绝不读取 mvp_test_*。'
  + `${writeGateHint.value}。页面不生成任何批次、阶段进度、入库记录或法条数据；未加载路由时不调用不存在的接口。`
)
const ingestionCapabilityHint = computed(() => {
  if (contractState.value !== 'ready') return 'GET /api/system/capabilities 未探测：能力字段以运行期响应为准，不提前假设。'
  if (capabilitiesState.value === 'error') return 'GET /api/system/capabilities 未返回能力声明，写操作按最严门控保持禁用。'
  const c = runtimeCapabilities.value?.ingestion
  if (!c) return '尚未读取到运行期 ingestion 能力声明（document_types / review_required / quality_required / manual_revision_export / auto_publish / write_configured）。'
  return `运行期能力：document_types=${(c.document_types || []).join('、') || '—'} · review_required=${c.review_required}`
    + ` · quality_required=${c.quality_required} · manual_revision_export=${c.manual_revision_export}`
    + ` · auto_publish=${c.auto_publish}（false 表示 STAGED 不自动发布） · admin_required=${c.admin_required}`
    + ` · write_configured=${c.write_configured}（configured 不等于数据库健康）`
})

function scrollToWrite() {
  document.getElementById('ingestion-write')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

const batchKbVersion = ref('')
const docsJson = ref('')
const fullSnapshot = ref(false)
const batchBusy = ref(false)
const batchIdempotencyKey = ref('')
const batchReceipt = ref<KnowledgeOperation | null>(null)
const pendingBatchBody = ref<IngestionBatchRequest | null>(null)

function newKey(): string {
  const c = globalThis.crypto
  return c && typeof c.randomUUID === 'function'
    ? c.randomUUID()
    : `mrp-${Date.now()}-${Math.random().toString(36).slice(2)}`
}

function parseBatchBody(): IngestionBatchRequest | null {
  if (!batchKbVersion.value.trim()) { ElMessage.warning('请填写目标 kb_version'); return null }
  let raw: unknown
  try { raw = JSON.parse(docsJson.value) } catch { ElMessage.error('documents 不是合法 JSON 数组'); return null }
  if (!Array.isArray(raw) || raw.length === 0) { ElMessage.warning('documents 必须是非空数组'); return null }
  const documents: IngestionDocument[] = []
  for (const item of raw as Record<string, unknown>[]) {
    if (!item || !String(item.parse_id || '').trim()) {
      ElMessage.warning('documents 每项都必须提供后端返回的 parse_id'); return null
    }
    documents.push({
      parse_id: String(item.parse_id),
      law_name: String(item.law_name ?? ''),
      law_id: String(item.law_id ?? ''),
      expected_review_version: Number(item.expected_review_version ?? 0)
    })
  }
  return { kb_version: batchKbVersion.value.trim(), documents, full_snapshot: fullSnapshot.value }
}

const precheck = useAsyncData<PrecheckResponse>((signal) => {
  if (!pendingBatchBody.value) throw new Error('尚未构造预检请求体')
  return ingestionPrecheck(pendingBatchBody.value, signal)
}, { immediate: false, isEmpty: () => false })
precheck.state.value = 'empty'
function runPrecheck() {
  const body = parseBatchBody()
  if (!body || !canPrecheck.value) return
  pendingBatchBody.value = body
  void precheck.load()
}
const canPrecheck = computed(() =>
  contractState.value === 'ready' && routePrecheck.value &&
  !!batchKbVersion.value.trim() && !!docsJson.value.trim() && !precheck.loading.value
)
const canCreateBatch = computed(() =>
  writeGateReady.value && !!batchKbVersion.value.trim() && !!docsJson.value.trim() && !batchBusy.value
)

async function runCreateBatch() {
  const body = parseBatchBody()
  if (!body || !canCreateBatch.value) return
  if (!batchIdempotencyKey.value) batchIdempotencyKey.value = newKey()
  batchBusy.value = true
  try {
    const receipt = await createIngestionBatch(body, batchIdempotencyKey.value)
    batchReceipt.value = receipt
    ElMessage.success('批次回执已返回；是否真正写入以 write_performed / outcome_unconfirmed 为准')
    // 结果确认后才换键；503 / 网络不明 / outcome_unconfirmed 沿用同键核对回执
    if (!receipt.outcome_unconfirmed) batchIdempotencyKey.value = newKey()
    void batches.load()
    void versions.load()
  } catch (err) {
    notifyApiError(err, '批次创建失败')
  } finally {
    batchBusy.value = false
  }
}

const releaseKbVersion = ref('')
const expectedActive = ref('')
const releaseBusy = ref(false)
const releaseIdempotencyKey = ref('')
const releaseReceipt = ref<KnowledgeOperation | null>(null)
const versionCheck = useAsyncData<VersionCheckResponse>(
  (signal) => ingestionVersionCheck(releaseKbVersion.value.trim(), signal),
  { immediate: false, isEmpty: () => false }
)
versionCheck.state.value = 'empty'
function runVersionCheck() {
  if (!canVersionCheck.value) return
  void versionCheck.load()
}
const canVersionCheck = computed(() =>
  contractState.value === 'ready' && routeVersionCheck.value &&
  !!releaseKbVersion.value.trim() && !versionCheck.loading.value
)
function canRelease(action: 'publish' | 'rollback'): boolean {
  const loaded = action === 'publish' ? routePublish.value : routeRollback.value
  return contractState.value === 'ready' && loaded && adminReady.value && writeConfigured.value &&
    !!releaseKbVersion.value.trim() && !releaseBusy.value
}
async function runRelease(action: 'publish' | 'rollback') {
  if (!canRelease(action)) return
  if (!releaseIdempotencyKey.value) releaseIdempotencyKey.value = newKey()
  releaseBusy.value = true
  try {
    const body = {
      kb_version: releaseKbVersion.value.trim(),
      expected_active_version: expectedActive.value.trim() || null
    }
    const receipt = action === 'publish'
      ? await publishKbVersion(body, releaseIdempotencyKey.value)
      : await rollbackKbVersion(body, releaseIdempotencyKey.value)
    releaseReceipt.value = receipt
    ElMessage.success('操作回执已返回；仍须重新查询当前 ACTIVE，不以历史回执当作当前指针')
    if (!receipt.outcome_unconfirmed) releaseIdempotencyKey.value = newKey()
    void versions.load()
  } catch (err) {
    notifyApiError(err, action === 'publish' ? '发布失败' : '回滚失败')
  } finally {
    releaseBusy.value = false
  }
}

const batches = useAsyncData<KnowledgeOperationPage>(
  (signal) => listIngestionBatches({ page: 1, pageSize: 20 }, signal), { immediate: false }
)
const batchDetail = ref<KnowledgeOperation | null>(null)
async function selectBatch(row: KnowledgeOperation | null) {
  batchDetail.value = null
  if (!row?.operation_id || !routeBatchGet.value) return
  try {
    batchDetail.value = await getIngestionBatch(row.operation_id)
  } catch (err) {
    notifyApiError(err, '批次详情加载失败')
  }
}

onMounted(async () => {
  if (contractState.value === 'ready') {
    await loadCapabilities()
    if (routeBatchesGet.value) void batches.load()
  }
})

function formatTime(v: string) { return v ? String(v).replace('T', ' ').slice(0, 19) : '—' }
</script>

<style scoped>
.header-tags { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.readonly-notice { margin-bottom: 12px; }
.ingest-form { display: flex; align-items: flex-start; gap: 10px; flex-wrap: wrap; }
.action-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin: 10px 0; }
.receipt-box { margin-top: 12px; padding: 10px; border: 1px solid var(--mr-line); border-radius: 6px; background: #fafbfe; }
.run-ready { color: var(--mr-st-success); }
.run-pending { color: var(--mr-text-3); }
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
.version-filters { display:flex; flex-wrap:wrap; gap:8px; margin-bottom:12px; }
.version-filters .el-input,.version-filters .el-select { width:180px; max-width:100%; }
</style>
