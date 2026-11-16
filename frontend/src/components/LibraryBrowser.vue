<template>
  <div class="lib-browser">
    <!-- 状态播报：加载 / 取消 / 空态 / 错误 / 门控态共用 aria-live -->
    <div class="lib-live" aria-live="polite" aria-atomic="true">{{ liveText }}</div>

    <!-- 筛选条：门控未通过时「文字说明 + 控件 disabled」双重可辨 -->
    <el-card shadow="never" class="lib-filter-card" data-lib-section="filter">
      <div class="lib-filter-row" role="group" aria-label="资料筛选">
        <span class="lib-filter-label">标题 / 文号 / 案号关键词</span>
        <el-input v-model="draft.query" size="small" maxlength="200" clearable :disabled="!canQuery"
          data-lib-field="query" aria-label="资料关键词" placeholder="输入标题、文号或案号" style="width: 210px"
          @keyup.enter="applyFilters" />
        <!-- 法规库整体隐藏 violation 控件（非仅禁用），也绝不发送该参数 -->
        <template v-if="isCase">
          <span class="lib-filter-label">违法行为</span>
          <el-input v-model="draft.violation" size="small" maxlength="200" clearable :disabled="!canQuery"
            data-lib-field="violation" aria-label="违法行为" placeholder="输入违法行为关键词" style="width: 190px" @keyup.enter="applyFilters" />
        </template>
        <!-- kb_version 仅 ADMIN 提供 -->
        <template v-if="isAdminIdentity">
          <span class="lib-filter-label">已发布版本</span>
          <el-input v-model="draft.kbVersion" size="small" maxlength="128" clearable :disabled="!canQuery"
            data-lib-field="kb_version" aria-label="知识库版本" placeholder="留空使用当前已发布版本" style="width: 200px"
            @keyup.enter="applyFilters" />
        </template>
        <span v-else class="lib-filter-label">当前已发布版本</span>
        <el-button size="small" type="primary" :disabled="!canQuery" @click="applyFilters">查询</el-button>
        <el-button size="small" :disabled="!canQuery" @click="resetFilters">清空筛选</el-button>
        <el-button size="small" :disabled="!canQuery" @click="runList">刷新</el-button>
      </div>
      <div class="filter-feedback" aria-live="polite">
        <span>已应用：{{ appliedSummary }}</span>
        <el-tag v-if="filtersDirty" type="warning" size="small">条件已修改，点击查询生效</el-tag>
      </div>
      <div class="mr-disabled-hint">{{ filterNote }}</div>
    </el-card>

    <!-- 运行期状态表：8 条 GET 方法级门控结果，静态契约信息，不发起任何业务请求 -->
    <details class="technical-details"><summary>接口与数据范围说明</summary>
    <el-card shadow="never" class="lib-routes-card" data-lib-section="routes">
      <template #header>
        <div class="card-head">
          <span>运行期接口状态 <span class="real-badge">REAL</span></span>
          <span class="card-sub">GET /api/openapi.json 方法级探测 · 路径存在 ≠ 方法可用</span>
        </div>
      </template>
      <div class="lib-scroll-x">
        <el-table class="lib-table lib-routes-table" data-lib-table="routes" :data="routeRows" size="small"
          :row-class-name="() => 'lib-route-row'">
          <el-table-column prop="method" label="方法" width="80" />
          <el-table-column prop="path" label="路径" min-width="330" show-overflow-tooltip />
          <el-table-column prop="page" label="用途" min-width="180" show-overflow-tooltip />
          <el-table-column label="运行期状态" width="130">
            <template #default="{ row }">
              <el-tag size="small" effect="plain"
                :type="row.status === 'loaded' ? 'success' : row.status === 'missing' ? 'warning' : 'info'">
                {{ row.statusText }}
              </el-tag>
            </template>
          </el-table-column>
        </el-table>
      </div>
      <div class="mr-disabled-hint" style="margin-top: 8px">
        draft-5 的 CapabilitiesResponse 未新增 library 字段，两页可用性只能靠
        hasRuntimeMethod('GET', path) 逐条判定；未加载时页面不发起请求、不展示演示数据。
        仅 ACTIVE / ARCHIVED 且有发布历史的版本可见：管理员全局、普通用户本人、审核员仅授权 owner。
      </div>
    </el-card>

    </details>

    <!-- 页内主从 + 面包屑：详情不注册路由，刷新即丢弃当前 id -->
    <el-breadcrumb v-if="view !== 'list'" separator="/" class="lib-crumbs">
      <el-breadcrumb-item>
        <el-link :underline="false" @click="backToList">{{ isCase ? '处罚案例库' : '法规库' }}</el-link>
      </el-breadcrumb-item>
      <el-breadcrumb-item v-if="view !== 'list'">
        <el-link v-if="view === 'article'" :underline="false" @click="backToParent">
          {{ activeRecord?.title || '详情' }}
        </el-link>
        <span v-else>{{ activeRecord?.title || '详情' }}</span>
      </el-breadcrumb-item>
      <el-breadcrumb-item v-if="view === 'article'"><span>条款正文</span></el-breadcrumb-item>
    </el-breadcrumb>

    <!-- ───────── 列表视图 ───────── -->
    <el-card v-if="view === 'list'" shadow="never" class="lib-list-card" data-lib-section="list">
      <template #header>
        <div class="card-head">
          <span>{{ listTitle }} <span class="real-badge">REAL</span></span>
          <span class="lib-result-meta">{{ listMeta }}</span>
        </div>
      </template>

      <LibraryStatePanel :query="listQuery" :show-back-list="true" @retry="runList" @back-list="runList">
        <!-- 窄屏 <768 降级为卡片列表 -->
        <div v-if="isNarrow" class="lib-card-list">
          <div v-for="row in listRows" :key="row.doc_version_id" class="lib-record-card lib-data-row"
            data-lib-row="record">
            <div class="lib-record-title">{{ row.title }}</div>
            <div class="lib-record-meta">
              <span>{{ isCase ? '案号' : '文号' }}：{{ fmt(row.number) }}</span>
              <el-tag size="small" effect="plain" :type="verificationTagType(row.verification_status)">
                {{ verificationLabel(row.verification_status) }}
              </el-tag>
            </div>
            <div class="lib-record-meta"><code class="mono">kb_version {{ fmt(row.kb_version) }}</code></div>
            <el-button size="small" type="primary" text @click="openDetailFromRow(row)">详情</el-button>
          </div>
        </div>
        <div v-else class="lib-scroll-x lib-list-table">
          <el-table class="lib-table lib-records-table" data-lib-table="list" :data="listRows" size="small"
            max-height="420" :row-class-name="() => 'lib-data-row'" @row-click="onRowClick">
            <el-table-column v-for="col in columns" :key="col.prop" :prop="col.prop" :label="col.label"
              :min-width="col.minWidth" :width="col.width" show-overflow-tooltip>
              <template #default="{ row }">
                <template v-if="col.prop === 'verification_status'">
                  <el-tag size="small" effect="plain" :type="verificationTagType(row.verification_status)">
                    {{ verificationLabel(row.verification_status) }}
                  </el-tag>
                </template>
                <template v-else-if="col.prop === 'kb_version'">
                  <code class="mono">{{ fmt(row.kb_version) }}</code>
                </template>
                <template v-else-if="col.prop === '__action'">
                  <el-button text size="small" type="primary" :disabled="!canQuery"
                    @click.stop="openDetailFromRow(row)">详情</el-button>
                </template>
                <template v-else>{{ fmt(row[col.prop]) }}</template>
              </template>
            </el-table-column>
          </el-table>
        </div>
        <div class="lib-pager">
          <el-pagination
            :current-page="page" :page-size="pageSize" :total="listQuery.data.value?.total || 0"
            :page-sizes="[10, 20, 50, 100]" layout="total, sizes, prev, pager, next"
            small background :disabled="!canQuery"
            @current-change="onPageChange" @size-change="onSizeChange" />
        </div>
        <div class="mr-disabled-hint" style="margin-top: 8px">
          doc_version_id 只存组件 state、只从列表 list[] 行取；点击行或「详情」进入页内主从视图，
          详情不注册独立路由。分页 total / page / page_size 均来自后端响应，前端不切片、不累计、
          不缓存上一身份的数据。核验状态 pending = 待核验、verified = 已核验；自动提取不标成已核验。
        </div>
      </LibraryStatePanel>
    </el-card>

    <!-- ───────── 详情视图（页内主从） ───────── -->
    <template v-else>
      <el-card shadow="never" class="lib-detail-card" data-lib-section="detail">
        <template #header>
          <div class="card-head">
            <span>{{ isCase ? '处罚案例详情' : '法规详情' }} <span class="real-badge">REAL</span></span>
            <span class="card-sub">{{ activeRecord?.title || '' }}</span>
          </div>
        </template>
        <LibraryStatePanel :query="detailQuery" :show-back-list="true" @retry="runDetail" @back-list="backToList">
          <template v-if="detailQuery.data.value">
            <el-descriptions :column="2" border size="small" class="lib-desc">
              <el-descriptions-item v-for="f in recordFields" :key="f.label" :label="f.label">
                <template v-if="f.key === 'verification_status'">
                  <el-tag size="small" effect="plain" :type="verificationTagType(f.value)">
                    {{ verificationLabel(f.value) }}
                  </el-tag>
                </template>
                <template v-else>{{ fmt(f.value) }}</template>
              </el-descriptions-item>
            </el-descriptions>
          </template>
        </LibraryStatePanel>
      </el-card>

      <template v-if="detailQuery.state.value === 'ready' && detailQuery.data.value">
        <!-- 原始 OCR 文本：纯文本 <pre>，禁止 v-html，与人工核验字段分框 -->
        <el-card shadow="never" class="lib-detail-card" data-lib-section="detail">
          <div class="lib-box-title">原始 OCR 文本（text_status={{ detailQuery.data.value.text_status }}）</div>
          <div class="mr-disabled-hint">{{ LIB_COPY.ocr }}</div>
          <pre class="lib-pre">{{ detailQuery.data.value.original_text || LIB_COPY.nullShort }}</pre>
        </el-card>

        <!-- 人工核验的结构化字段：与 OCR 单独分框 -->
        <el-card shadow="never" class="lib-detail-card" data-lib-section="detail">
          <div class="lib-box-title">{{ isCase ? '人工核验的结构化字段（案例）' : '人工核验的结构化字段' }}</div>
          <template v-if="isCase">
            <div class="lib-field-grid">
              <div v-for="f in caseFields" :key="f.key" class="lib-field">
                <span class="lib-field-key">{{ f.label }}</span>
                <span class="lib-field-val">{{ f.value }}</span>
              </div>
            </div>
            <div class="mr-disabled-hint">{{ LIB_COPY.penalty }}</div>
            <div class="lib-box-title" style="margin-top: 10px">field_sources（后端原始字段）</div>
            <pre class="lib-pre">{{ pretty(caseStructured.field_sources) }}</pre>
          </template>
          <template v-else>
            <div v-if="detailQuery.data.value.structured" class="lib-field-grid">
              <div v-for="f in genericStructuredFields" :key="f.key" class="lib-field">
                <span class="lib-field-key">{{ f.key }}</span>
                <span class="lib-field-val">{{ f.value }}</span>
              </div>
            </div>
            <div v-else class="lib-null">{{ LIB_COPY.nullShort }}</div>
          </template>
          <div class="mr-disabled-hint">{{ LIB_COPY.nullField }}</div>
        </el-card>

        <!-- 原始证据文件：source_url 仍需 Bearer，只走认证 Axios → Blob URL -->
        <el-card shadow="never" class="lib-detail-card" data-lib-section="detail">
          <div class="lib-box-title">原始证据文件</div>
          <div class="source-hint">
            后端返回 source_url：<code class="mono">{{ detailQuery.data.value.source_url }}</code>。该地址仍需 Bearer，
            绝不能直接塞进 iframe / img；原件字节由认证 Axios 读取后生成 Blob URL，切换对象或离开时 revoke。
            source_file_id 来自列表行，不拼接推导。
          </div>
          <div class="lib-source-actions">
            <el-button size="small" :loading="sourceLoading" @click="viewSource">查看原件</el-button>
            <el-button size="small" @click="downloadOriginal">下载原件</el-button>
            <el-button v-if="sourceUrl" size="small" @click="releaseSource">关闭预览并释放 Blob URL</el-button>
          </div>
          <el-alert v-if="sourceError" type="error" :closable="false" role="alert"
            title="原件读取失败" :description="sourceError" />
          <div v-if="sourceUrl" class="lib-source-frame">
            <iframe v-if="sourceKind === 'pdf'" :src="sourceUrl" title="原始 PDF 预览（已认证 Blob URL）" />
            <img v-else-if="sourceKind === 'image'" :src="sourceUrl" alt="原始图片预览（已认证 Blob URL）" />
            <div v-else class="lib-source-fallback">该格式后端仅支持授权下载，不提供内联预览。</div>
          </div>
        </el-card>

        <!-- 子列表：法规库 = 章节 / 条款；案例库 = 处罚依据引用（各自独立查询实例 + 独立门控） -->
        <el-card shadow="never" class="lib-detail-card" data-lib-section="detail">
          <div class="lib-box-title">{{ isCase ? '处罚依据引用（references）' : '章节 / 条款' }}</div>
          <el-tabs v-model="activeTab" @tab-change="onTabChange">
            <el-tab-pane v-if="!isCase" label="章节（chapters）" name="chapters" />
            <el-tab-pane v-if="!isCase" label="条款（articles）" name="articles" />
            <el-tab-pane v-if="isCase" label="处罚依据引用（references）" name="references" />
          </el-tabs>
          <div class="mr-disabled-hint">{{ partsHint }}</div>
          <LibraryStatePanel :query="partsQuery" :show-back-list="true" neutral-text="尚未发起子列表查询。"
            @retry="runParts" @back-list="backToList">
            <div v-if="isNarrow" class="lib-card-list">
              <div v-for="(row, i) in partRows" :key="i" class="lib-record-card">
                <div v-for="c in partNarrowFields" :key="c.prop" class="lib-record-meta">
                  <span>{{ c.label }}：</span><span>{{ fmt(row[c.prop]) }}</span>
                </div>
                <el-button v-if="activeTab === 'articles'" size="small" type="primary" text
                  :disabled="!articleRouteReady" @click="openArticle(row)">条款正文</el-button>
              </div>
            </div>
            <div v-else class="lib-scroll-x">
              <el-table class="lib-table" :data="partRows" size="small" max-height="260">
                <template v-if="activeTab === 'chapters'">
                  <el-table-column prop="chapter_id" label="chapter_id" min-width="180" show-overflow-tooltip />
                  <el-table-column label="number" min-width="110"><template #default="{ row }">{{ fmt(row.number) }}</template></el-table-column>
                  <el-table-column label="title" min-width="200"><template #default="{ row }">{{ fmt(row.title) }}</template></el-table-column>
                  <el-table-column label="ordinal" width="100"><template #default="{ row }">{{ fmt(row.ordinal) }}</template></el-table-column>
                </template>
                <template v-else-if="activeTab === 'articles'">
                  <el-table-column prop="article_id" label="article_id" min-width="180" show-overflow-tooltip />
                  <el-table-column label="chapter_id" min-width="150"><template #default="{ row }">{{ fmt(row.chapter_id) }}</template></el-table-column>
                  <el-table-column label="number" min-width="100"><template #default="{ row }">{{ fmt(row.number) }}</template></el-table-column>
                  <el-table-column label="title" min-width="180"><template #default="{ row }">{{ fmt(row.title) }}</template></el-table-column>
                  <el-table-column label="ordinal" width="90"><template #default="{ row }">{{ fmt(row.ordinal) }}</template></el-table-column>
                  <el-table-column label="操作" width="110" fixed="right">
                    <template #default="{ row }">
                      <el-button text size="small" type="primary" :disabled="!articleRouteReady"
                        @click="openArticle(row)">条款正文</el-button>
                    </template>
                  </el-table-column>
                </template>
                <template v-else>
                  <el-table-column prop="reference_id" label="reference_id" min-width="160" show-overflow-tooltip />
                  <el-table-column label="law_version_id" min-width="150"><template #default="{ row }">{{ fmt(row.law_version_id) }}</template></el-table-column>
                  <el-table-column label="article_id" min-width="150"><template #default="{ row }">{{ fmt(row.article_id) }}</template></el-table-column>
                  <el-table-column label="citation（原样）" min-width="200"><template #default="{ row }">{{ fmt(row.citation) }}</template></el-table-column>
                  <el-table-column label="source" min-width="120"><template #default="{ row }">{{ fmt(row.source) }}</template></el-table-column>
                  <el-table-column label="method（原样）" min-width="120"><template #default="{ row }">{{ fmt(row.method) }}</template></el-table-column>
                  <el-table-column label="核验状态" width="140">
                    <template #default="{ row }">
                      <el-tag size="small" effect="plain" :type="verificationTagType(row.verification_status)">
                        {{ verificationLabel(row.verification_status) }}
                      </el-tag>
                    </template>
                  </el-table-column>
                </template>
              </el-table>
            </div>
            <div class="lib-pager">
              <el-pagination :current-page="partPage" :page-size="partPageSize"
                :total="partsQuery.data.value?.total || 0" layout="total, prev, pager, next" small background
                @current-change="onPartPageChange" />
            </div>
          </LibraryStatePanel>
        </el-card>

        <!-- 条款正文：仅法规库；doc_version_id 取自列表行、article_id 取自条款行 -->
        <el-card v-if="!isCase && activeArticleId" shadow="never" class="lib-detail-card" data-lib-section="detail">
          <div class="lib-box-title">条款正文（GET /api/library/laws/{doc_version_id}/articles/{article_id}）</div>
          <LibraryStatePanel :query="articleQuery" :show-back-parent="true" :show-back-list="true"
            neutral-text="尚未发起条款正文查询。"
            @retry="runArticle" @back-parent="backToParent" @back-list="backToList">
            <template v-if="articleQuery.data.value">
              <div class="lib-field-grid">
                <div v-for="f in articleFields" :key="f.key" class="lib-field">
                  <span class="lib-field-key">{{ f.label }}</span>
                  <span class="lib-field-val">{{ f.value }}</span>
                </div>
              </div>
              <div class="mr-disabled-hint">{{ LIB_COPY.charRange }}</div>
              <div class="lib-box-title" style="margin-top: 10px">原始 OCR 文本（后端已按字符范围切片）</div>
              <div class="mr-disabled-hint">{{ LIB_COPY.ocr }}</div>
              <pre class="lib-pre">{{ articleQuery.data.value.original_text || LIB_COPY.nullShort }}</pre>
            </template>
          </LibraryStatePanel>
        </el-card>
      </template>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useAppStore } from '@/stores/app'
import { hasToken } from '@/api/client'
import { onAuthStateChange } from '@/api/authEvents'
import { contractState, hasLibraryRoute, probeContract } from '@/api/dataSource'
import { isAdminIdentity, principal, principalLoadedAt } from '@/api/principal'
import {
  createSourceUrl, downloadSourceFile, getSourceFile, isValidFileId, revokeSourceUrl,
  type SourceKind
} from '@/api/documentFiles'
import {
  LIBRARY_ARTICLE_PATH, LIBRARY_ARTICLES_PATH, LIBRARY_CHAPTERS_PATH, LIBRARY_DETAIL_PATHS,
  LIBRARY_LIST_PATHS, LIBRARY_REFERENCES_PATH, LIBRARY_ROUTES, getLibraryArticle, getLibraryCase,
  getLibraryLaw, listLibraryArticles, listLibraryCases, listLibraryChapters, listLibraryLaws,
  listLibraryReferences
} from '@/api/library'
import {
  LIB_COPY, verificationLabel, verificationTagType
} from '@/views/library/copy'
import LibraryStatePanel from '@/views/library/LibraryStatePanel.vue'
import { useLibraryQuery } from '@/views/library/useLibraryQuery'
import type {
  LibraryArticle, LibraryArticleStructured, LibraryCaseStructured, LibraryChapter,
  LibraryDetail, LibraryKind, LibraryList, LibraryParts, LibraryQuery, LibraryRecord,
  LibraryReference
} from '@/api/types'

/**
 * v0.2.3 draft-5 法规库 / 处罚案例库共用只读骨架（Phase 2 定稿）。
 *
 * - 页面局部 useLibraryQuery：自定义状态联合类型，不复用 LoadState；按 status + code 映射，
 *   门控先行（hasToken → probeContract → hasRuntimeMethod），绝不从响应 404 反推契约状态。
 * - L1/L2 两层渲染：L1 自管门控态 / 全部错误态 / unpublished；L2 AsyncPanel 只接三态。
 * - 页内主从 + 面包屑，详情不注册路由；每级详情独立查询实例 + 独立方法级门控。
 * - 法规库整体隐藏 violation、不发送该参数；kb_version 仅 ADMIN 提供；
 *   筛选提交冻结快照，分页只透传 page / page_size，返回列表保留快照但重新请求。
 * - 身份 / 凭证变化清空全部 data、筛选快照、当前 id 并重新检查运行期契约。
 */
const props = defineProps<{ kind: LibraryKind }>()

const isCase = computed(() => props.kind === 'case')
const listPath = LIBRARY_LIST_PATHS[props.kind]
const detailPath = LIBRARY_DETAIL_PATHS[props.kind]
const store = useAppStore()

function fmt(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}
function pretty(value: unknown): string {
  if (value === null || value === undefined || value === '') return LIB_COPY.nullShort
  if (typeof value === 'object') return JSON.stringify(value, null, 2)
  return String(value)
}

/* ───────── 筛选快照（提交时冻结，同 SearchView.submittedFilters） ───────── */

const draft = reactive({ query: '', violation: '', kbVersion: '' })
const submitted = ref<LibraryQuery>({ page: 1, pageSize: 20 })
const page = ref(1)
const pageSize = ref(20)

function snapshot(p: number, size: number): LibraryQuery {
  return {
    page: p,
    pageSize: size,
    query: draft.query.trim() || undefined,
    violation: isCase.value ? (draft.violation.trim() || undefined) : undefined,
    kbVersion: isAdminIdentity.value ? (draft.kbVersion.trim() || undefined) : undefined
  }
}

const appliedSummary = computed(() => [submitted.value.query && `关键词：${submitted.value.query}`, submitted.value.violation && `违法行为：${submitted.value.violation}`, submitted.value.kbVersion && `版本：${submitted.value.kbVersion}`].filter(Boolean).join('；') || '全部可见资料 · 当前已发布版本')
const filtersDirty = computed(() => JSON.stringify(snapshot(page.value, pageSize.value)) !== JSON.stringify(submitted.value))
const filterNote = computed(() => LIB_COPY.filterNote(isCase.value, isAdminIdentity.value))

function closeDetailForFilter() {
  view.value = 'list'
  activeRecord.value = null
  activeArticleId.value = ''
  releaseSource()
  detailQuery.clear()
  partsQuery.clear()
  articleQuery.clear()
}

function applyFilters() {
  if (!canQuery.value) return
  closeDetailForFilter()
  page.value = 1
  submitted.value = snapshot(1, pageSize.value)
  runList()
}
function resetFilters() {
  closeDetailForFilter()
  draft.query = ''
  draft.violation = ''
  draft.kbVersion = ''
  page.value = 1
  submitted.value = { page: 1, pageSize: pageSize.value }
  if (canQuery.value) runList()
}
function onPageChange(p: number) {
  page.value = p
  submitted.value = { ...submitted.value, page: p, pageSize: pageSize.value }
  runList()
}
function onSizeChange(size: number) {
  pageSize.value = size
  page.value = 1
  submitted.value = { ...submitted.value, page: 1, pageSize: size }
  runList()
}

/* ───────── 每级独立查询实例 ───────── */

const listQuery = useLibraryQuery<LibraryList>({
  path: () => listPath,
  fetcher: (signal) => (isCase.value
    ? listLibraryCases(submitted.value, signal)
    : listLibraryLaws(submitted.value, signal)),
  detectUnpublished: true
})

const view = ref<'list' | 'detail' | 'article'>('list')
const activeRecord = ref<LibraryRecord | null>(null)
const activeArticleId = ref('')
const activeTab = ref<'chapters' | 'articles' | 'references'>(isCase.value ? 'references' : 'chapters')
const partPage = ref(1)
const partPageSize = 20
let focusRowIndex = -1

const partsPath = computed(() => {
  if (isCase.value) return LIBRARY_REFERENCES_PATH
  return activeTab.value === 'chapters' ? LIBRARY_CHAPTERS_PATH : LIBRARY_ARTICLES_PATH
})
const articleRouteReady = computed(() => hasLibraryRoute(LIBRARY_ARTICLE_PATH))

const detailQuery = useLibraryQuery<LibraryDetail>({
  path: () => detailPath,
  fetcher: (signal) => {
    const id = activeRecord.value?.doc_version_id || ''
    const q = { kbVersion: submitted.value.kbVersion }
    return isCase.value ? getLibraryCase(id, q, signal) : getLibraryLaw(id, q, signal)
  },
  isEmpty: () => false
})

const partsQuery = useLibraryQuery<LibraryParts<LibraryChapter | LibraryArticle | LibraryReference>>({
  path: () => partsPath.value,
  fetcher: (signal) => {
    const id = activeRecord.value?.doc_version_id || ''
    const q = { page: partPage.value, pageSize: partPageSize, kbVersion: submitted.value.kbVersion }
    if (isCase.value) return listLibraryReferences(id, q, signal)
    return activeTab.value === 'chapters'
      ? listLibraryChapters(id, q, signal)
      : listLibraryArticles(id, q, signal)
  }
})

const articleQuery = useLibraryQuery<LibraryDetail>({
  path: () => LIBRARY_ARTICLE_PATH,
  fetcher: (signal) => getLibraryArticle(
    activeRecord.value?.doc_version_id || '', activeArticleId.value,
    { kbVersion: submitted.value.kbVersion }, signal
  ),
  isEmpty: () => false
})

function runList() { void listQuery.run() }
function runDetail() { void detailQuery.run() }
function runParts() { void partsQuery.run() }
function runArticle() { void articleQuery.run() }

/**
 * 控件可用性只由列表层级的方法级门控决定；错误态不禁用控件（便于改筛选后重新查询）。
 * 声明位置放在四个查询实例之后，避免闭包在实例创建前求值。
 */
const canQuery = computed(() => !listQuery.state.value.startsWith('gating-'))

/* ───────── 运行期状态表 ───────── */

function routeStatus(path: string): 'loaded' | 'missing' | 'unknown' {
  const probed = contractState.value
  // 只有探测失败才是「未探测」；ready / outdated 都已拿到运行期方法清单，
  // 后者同样应逐条给出「未加载」，不能整表退化成 info 态。
  if (probed === 'unknown' || probed === 'unavailable' || probed === 'error' || probed === 'no-permission') {
    return 'unknown'
  }
  return hasLibraryRoute(path) ? 'loaded' : 'missing'
}
const routeRows = computed(() => LIBRARY_ROUTES.map((route) => {
  const status = routeStatus(route.path)
  return {
    method: route.method,
    path: route.path,
    page: route.page,
    status,
    statusText: status === 'loaded' ? '已加载' : status === 'missing' ? '未加载' : '未探测'
  }
}))

/* ───────── 列表呈现 ───────── */

interface LibColumn { prop: string; label: string; minWidth?: number; width?: number }
const columns = computed<LibColumn[]>(() => [
  { prop: 'title', label: isCase.value ? '案例标题' : '法规标题', minWidth: 240 },
  { prop: 'number', label: isCase.value ? '案号' : '文号', minWidth: 140 },
  { prop: 'category', label: '分类', minWidth: 120 },
  ...(isCase.value
    ? [{ prop: 'published_on', label: '发布时间', minWidth: 140 }]
    : [{ prop: 'authority', label: '发布机关', minWidth: 160 }, { prop: 'effective_status', label: '效力状态', minWidth: 120 }]),
  { prop: 'verification_status', label: '核验状态', width: 130 },
  { prop: 'kb_version', label: 'kb_version', width: 150 },
  { prop: '__action', label: '操作', width: 90 }
])

const listRows = computed<LibraryRecord[]>(() => listQuery.data.value?.list || [])
const partRows = computed(() => (partsQuery.data.value?.list || []) as unknown as Record<string, unknown>[])
const partNarrowFields = computed<Array<{ prop: string; label: string }>>(() => {
  if (activeTab.value === 'chapters') {
    return [
      { prop: 'chapter_id', label: 'chapter_id' }, { prop: 'number', label: 'number' },
      { prop: 'title', label: 'title' }, { prop: 'ordinal', label: 'ordinal' }
    ]
  }
  if (activeTab.value === 'articles') {
    return [
      { prop: 'article_id', label: 'article_id' }, { prop: 'chapter_id', label: 'chapter_id' },
      { prop: 'number', label: 'number' }, { prop: 'title', label: 'title' }, { prop: 'ordinal', label: 'ordinal' }
    ]
  }
  return [
    { prop: 'reference_id', label: 'reference_id' }, { prop: 'law_version_id', label: 'law_version_id' },
    { prop: 'article_id', label: 'article_id' }, { prop: 'citation', label: 'citation' },
    { prop: 'source', label: 'source' }, { prop: 'method', label: 'method' },
    { prop: 'verification_status', label: '核验状态' }
  ]
})

const listTitle = computed(() => (isCase.value ? '处罚案例列表' : '法规列表'))
const listMeta = computed(() => {
  const d = listQuery.data.value
  return d
    ? `共 ${d.total} 条 · 第 ${d.page} 页 · 每页 ${d.page_size} 条 · 版本 ${d.kb_version || '尚未发布'}`
    : `GET ${listPath} · 尚未加载`
})
const partsHint = computed(() => isCase.value
  ? '引用列表的 citation 与 method 原样展示，不推断法律效力；law_version_id 不是 doc_version_id，本页不据此拼接条款正文请求。子列表分页来自后端响应。'
  : '章节 / 条款分页来自后端响应；条款正文的 doc_version_id 取自列表行、article_id 取自条款行，均由后端返回，不拼接推导。')

/* ───────── 页内主从导航 ───────── */

function restoreFocus() {
  if (focusRowIndex < 0) return
  void nextTick(() => {
    // 宽屏表格行 / 窄屏卡片行都支持焦点回归
    const rows = document.querySelectorAll(
      '.lib-records-table .el-table__body-wrapper tr.el-table__row, .lib-card-list .lib-record-card'
    )
    const el = rows[focusRowIndex] as HTMLElement | undefined
    if (el) {
      el.tabIndex = -1
      el.focus()
    }
  })
}

/** 统一由列表行进入详情：索引从 listRows 计算，避免把 MouseEvent 当作索引 */
function openDetailFromRow(row: LibraryRecord) {
  const index = listRows.value.findIndex((r) => r.doc_version_id === row.doc_version_id)
  openDetail(row, index)
}

function openDetail(row: LibraryRecord, index: number) {
  if (!row || !row.doc_version_id) return
  focusRowIndex = index
  activeRecord.value = row
  activeArticleId.value = ''
  activeTab.value = isCase.value ? 'references' : 'chapters'
  partPage.value = 1
  releaseSource()
  detailQuery.clear()
  partsQuery.clear()
  articleQuery.clear()
  view.value = 'detail'
  void detailQuery.run()
  void partsQuery.run()
}

function onRowClick(row: LibraryRecord, _column: unknown, event: MouseEvent) {
  if ((event?.target as HTMLElement | null)?.closest('button')) return
  const index = listRows.value.findIndex((r) => r.doc_version_id === row.doc_version_id)
  openDetail(row, index)
}

function backToList() {
  view.value = 'list'
  activeRecord.value = null
  activeArticleId.value = ''
  releaseSource()
  detailQuery.clear()
  partsQuery.clear()
  articleQuery.clear()
  // 保留筛选快照但重新请求，不复用旧响应
  runList()
  restoreFocus()
}

function backToParent() {
  if (view.value === 'article') {
    view.value = 'detail'
    activeArticleId.value = ''
    articleQuery.clear() // 只清当前层级，保留详情与列表
  } else {
    backToList()
  }
}

function openArticle(row: Record<string, unknown>) {
  if (!articleRouteReady.value) return
  const id = String(row.article_id || '')
  if (!id) return
  activeArticleId.value = id
  articleQuery.clear()
  view.value = 'article'
  void articleQuery.run()
}

function onTabChange() {
  partPage.value = 1
  activeArticleId.value = ''
  articleQuery.clear()
  if (view.value === 'article') view.value = 'detail'
  void partsQuery.run()
}
function onPartPageChange(p: number) {
  partPage.value = p
  runParts()
}

/* ───────── 详情字段 ───────── */

const recordFields = computed(() => {
  const r = activeRecord.value
  if (!r) return []
  const entries: Array<[string, string, unknown]> = [
    ['doc_version_id', 'doc_version_id', r.doc_version_id],
    ['kind', 'kind', r.kind],
    ['title', 'title', r.title],
    ['number', 'number（文号 / 案号）', r.number],
    ['category', 'category', r.category],
    ['authority', 'authority（发布机关）', r.authority],
    ['published_on', 'published_on', r.published_on],
    ['effective_on', 'effective_on', r.effective_on],
    ['repealed_on', 'repealed_on', r.repealed_on],
    ['effective_status', 'effective_status', r.effective_status],
    ['verification_status', 'verification_status（核验状态）', r.verification_status],
    ['owner_id', 'owner_id', r.owner_id],
    ['document_id', 'document_id', r.document_id],
    ['source_file_id', 'source_file_id', r.source_file_id],
    ['parse_id', 'parse_id', r.parse_id],
    ['kb_version', 'kb_version', r.kb_version]
  ]
  return entries.map(([key, label, value]) => ({ key, label, value }))
})

const caseStructured = computed(() => (detailQuery.data.value?.structured || {}) as LibraryCaseStructured)
const caseFields = computed(() => {
  const s = caseStructured.value
  return [
    { key: 'region', label: 'region（地域）', value: fmt(s.region) },
    { key: 'violation', label: 'violation（违法行为）', value: fmt(s.violation) },
    { key: 'facts', label: 'facts（事实）', value: fmt(s.facts) },
    { key: 'investigation', label: 'investigation（调查）', value: fmt(s.investigation) },
    { key: 'evidence_summary', label: 'evidence_summary（证据摘要）', value: fmt(s.evidence_summary) },
    { key: 'penalty_type', label: 'penalty_type（处罚类型）', value: fmt(s.penalty_type) },
    { key: 'penalty_amount', label: 'penalty_amount（原样十进制字符串）', value: fmt(s.penalty_amount) },
    { key: 'penalty_result', label: 'penalty_result（处罚结果）', value: fmt(s.penalty_result) }
  ]
})
const genericStructuredFields = computed(() =>
  Object.entries(detailQuery.data.value?.structured || {}).map(([key, value]) => ({ key, value: pretty(value) }))
)
const articleFields = computed(() => {
  const s = (articleQuery.data.value?.structured || {}) as LibraryArticleStructured
  return [
    { key: 'article_id', label: 'article_id', value: fmt(s.article_id) },
    { key: 'chapter_id', label: 'chapter_id', value: fmt(s.chapter_id) },
    { key: 'number', label: 'number', value: fmt(s.number) },
    { key: 'title', label: 'title', value: fmt(s.title) },
    { key: 'ordinal', label: 'ordinal', value: fmt(s.ordinal) },
    { key: 'raw_start', label: 'raw_start（字符位置，零基）', value: fmt(s.raw_start) },
    { key: 'raw_end', label: 'raw_end（字符位置，左闭右开）', value: fmt(s.raw_end) },
    { key: 'page_start', label: 'page_start', value: fmt(s.page_start) },
    { key: 'page_end', label: 'page_end', value: fmt(s.page_end) },
    { key: 'chunk_ids', label: 'chunk_ids[]', value: pretty(s.chunk_ids) }
  ]
})

/* ───────── 原始证据文件（Blob URL 生命周期） ───────── */

const sourceUrl = ref('')
const sourceKind = ref<SourceKind>('other')
const sourceError = ref('')
const sourceLoading = ref(false)
let sourceCtrl: AbortController | null = null

function releaseSource() {
  if (sourceCtrl) { sourceCtrl.abort(); sourceCtrl = null }
  if (sourceUrl.value) { revokeSourceUrl(sourceUrl.value); sourceUrl.value = '' }
  sourceKind.value = 'other'
  sourceLoading.value = false
  sourceError.value = ''
}

async function viewSource() {
  releaseSource()
  const rec = activeRecord.value
  const d = detailQuery.data.value
  if (!rec || !d) return
  if (!isValidFileId(rec.source_file_id)) {
    sourceError.value = LIB_COPY.sourceError
    return
  }
  const ctrl = new AbortController()
  sourceCtrl = ctrl
  sourceLoading.value = true
  try {
    // 认证 Axios ArrayBuffer → Blob URL；source_url 绝不直接塞进 iframe / img
    const file = await getSourceFile(rec.source_file_id, d.original_file_name, ctrl.signal)
    if (ctrl.signal.aborted) return
    sourceUrl.value = createSourceUrl(file)
    sourceKind.value = file.kind
  } catch {
    if (ctrl.signal.aborted) return
    sourceError.value = LIB_COPY.sourceError
  } finally {
    if (sourceCtrl === ctrl) { sourceCtrl = null; sourceLoading.value = false }
  }
}

async function downloadOriginal() {
  const rec = activeRecord.value
  const d = detailQuery.data.value
  if (!rec || !d) return
  try {
    await downloadSourceFile(rec.source_file_id, d.original_file_name || rec.source_file_id)
  } catch {
    sourceError.value = LIB_COPY.sourceError
  }
}

/* ───────── 状态播报 ───────── */

const liveText = computed(() => {
  if (view.value !== 'list') return `详情视图：${activeRecord.value?.title || ''}`
  switch (listQuery.state.value) {
    case 'gating-no-token': return '未配置凭证：未发起请求'
    case 'gating-contract': return '运行期契约未就绪：未发起请求'
    case 'gating-route': return '运行期未加载该接口：未发起请求'
    case 'loading': return '正在从后端加载真实数据…'
    case 'unpublished': return '合法空态：status=unpublished'
    case 'empty': return '未找到符合条件的数据（后端返回空列表）'
    case 'ready': return `已加载 ${listQuery.data.value?.list.length || 0} 条真实记录`
    case 'canceled': return '请求已取消'
    case 'not-found-404': return '未找到对象（404）'
    case 'auth-401': return '未认证 / 无权限'
    case 'invalid-422': return '参数不被接受（422）'
    case 'schema-503': return '新库 Schema 未安装（503）'
    default: return '服务暂不可用'
  }
})

/* ───────── 身份 / 凭证变化：清空全部 data、筛选快照、当前 id ───────── */

function resetAll() {
  listQuery.clear()
  detailQuery.clear()
  partsQuery.clear()
  articleQuery.clear()
  view.value = 'list'
  activeRecord.value = null
  activeArticleId.value = ''
  partPage.value = 1
  focusRowIndex = -1
  draft.query = ''
  draft.violation = ''
  draft.kbVersion = ''
  page.value = 1
  pageSize.value = 20
  submitted.value = { page: 1, pageSize: 20 }
  releaseSource()
  if (hasToken()) void probeContract().then(() => runList())
}

watch(() => store.token, (now, was) => { if (now !== was) resetAll() })
watch(() => principal.value?.principal_id ?? '', (now, was) => {
  if (was && now && now !== was) resetAll()
})
watch(() => principalLoadedAt.value, (now, was) => {
  if (now && was && now !== was) resetAll()
})
const stopAuthListener = onAuthStateChange((status) => {
  if (status === 401 || status === 403) resetAll()
})

/* ───────── 窄屏 <768 表格降级 ───────── */

const isNarrow = ref(false)
let narrowMql: MediaQueryList | null = null
function onNarrowChange(e: MediaQueryListEvent) { isNarrow.value = e.matches }

onMounted(() => {
  narrowMql = window.matchMedia('(max-width: 767px)')
  isNarrow.value = narrowMql.matches
  narrowMql.addEventListener('change', onNarrowChange)
  void listQuery.run()
})

onBeforeUnmount(() => {
  narrowMql?.removeEventListener('change', onNarrowChange)
  stopAuthListener()
  releaseSource()
})
</script>
